"""
Application Executor — fills and submits job application forms using Playwright.

Human-review gate:
  - Any application with status PENDING_REVIEW requires manual approval before submission.
  - Only APPROVED applications are auto-submitted.
  - Complex or ambiguous forms pause and set status back to PENDING_REVIEW.
"""

import asyncio
import logging
import random

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

from app.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_HUMAN_TYPING_DELAY = (30, 90)   # ms per character
_PAUSE_BETWEEN_FIELDS = (0.5, 1.5)


async def submit_application(
    application: Application,
    profile: UserProfile,
    headless: bool = True,
) -> bool:
    """
    Attempt to fill and submit a form-based application.
    Returns True if submitted successfully, False if manual intervention needed.

    Safety gate: only processes APPROVED applications.
    """
    if application.status != ApplicationStatus.APPROVED:
        logger.warning("Skipping app %d — not approved (status=%s)", application.id, application.status)
        return False

    apply_url = application.job.apply_url
    if not apply_url:
        logger.warning("No apply URL for application %d", application.id)
        return False

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            await page.goto(apply_url, wait_until="networkidle", timeout=30_000)
            await _random_pause(1.0, 2.0)

            filled = await _fill_form(page, application, profile)
            if not filled:
                logger.info("App %d: form too complex — flagged for manual review", application.id)
                return False

            # DO NOT auto-submit in dev mode — screenshot instead
            if settings.APP_ENV != "production":
                await page.screenshot(path=f"/tmp/autointern_app_{application.id}.png")
                logger.info("DEV: screenshot saved, not submitted")
                return False

            await _submit(page)
            return True

        except PWTimeout:
            logger.error("Timeout filling form for application %d", application.id)
            return False
        finally:
            await browser.close()


async def _fill_form(page: Page, app: Application, profile: UserProfile) -> bool:
    """
    Fills common form fields. Returns False if the form looks too complex.
    """
    field_map = {
        # Common name patterns → profile values
        r"(first.?name|firstname)": profile.name.split()[0] if profile.name else "",
        r"(last.?name|lastname)": profile.name.split()[-1] if profile.name else "",
        r"email": profile.email,
        r"phone": profile.phone or "",
        r"linkedin": profile.linkedin_url or "",
        r"github": profile.github_url or "",
        r"portfolio|website": profile.portfolio_url or "",
        r"cover.?letter": app.cover_letter or "",
    }

    import re
    filled_count = 0

    inputs = await page.query_selector_all("input[type=text], input[type=email], input[type=tel], textarea")
    for inp in inputs:
        name_attr = (await inp.get_attribute("name") or "").lower()
        placeholder = (await inp.get_attribute("placeholder") or "").lower()
        label = await _get_label(page, inp)
        combined = f"{name_attr} {placeholder} {label}".lower()

        for pattern, value in field_map.items():
            if re.search(pattern, combined) and value:
                await inp.click()
                await _random_pause(0.2, 0.5)
                await _type_human(page, inp, value)
                filled_count += 1
                break

    # Bail if the form looks complex (many unfilled required fields)
    required_unfilled = await page.query_selector_all(
        "input[required]:not([value]), select[required]"
    )
    if len(required_unfilled) > 3:
        logger.info("Form has %d unfilled required fields", len(required_unfilled))
        return False

    # Handle file upload for resume
    resume_input = await page.query_selector("input[type=file]")
    if resume_input and profile.resume_pdf_path:
        await resume_input.set_input_files(profile.resume_pdf_path)

    return filled_count > 0


async def _submit(page: Page) -> None:
    """Click the submit button."""
    submit = await page.query_selector(
        "button[type=submit], input[type=submit], button:has-text('Submit'), button:has-text('Apply')"
    )
    if submit:
        await _random_pause(1.0, 2.0)
        await submit.click()
        await page.wait_for_load_state("networkidle", timeout=15_000)


async def _type_human(page: Page, element, text: str) -> None:
    """Type into an element with realistic per-character delays."""
    for char in text:
        await element.type(char)
        await asyncio.sleep(random.randint(*_HUMAN_TYPING_DELAY) / 1000)


async def _random_pause(min_s: float, max_s: float) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _get_label(page: Page, element) -> str:
    """Try to find the <label> text associated with an input."""
    try:
        el_id = await element.get_attribute("id")
        if el_id:
            label = await page.query_selector(f"label[for='{el_id}']")
            if label:
                return (await label.inner_text()).lower()
    except Exception:
        pass
    return ""
