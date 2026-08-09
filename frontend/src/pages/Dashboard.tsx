import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerScrape, triggerResearch, triggerJobsScrape, triggerEnrichEmails } from "../api";
import ApplicationTable from "../components/ApplicationTable";
import OpportunityFeed from "../components/OpportunityFeed";

export default function Dashboard() {
  const qc = useQueryClient();

  const scrapeMut = useMutation({
    mutationFn: triggerScrape,
    onSuccess: (data) => {
      alert(`Scraped ${data.scraped} companies`);
      qc.invalidateQueries({ queryKey: ["top-jobs"] });
    },
  });

  const researchMut = useMutation({
    mutationFn: triggerResearch,
    onSuccess: (data) => alert(`Researched ${data.researched} companies`),
  });

  const scrapeJobsMut = useMutation({
    mutationFn: triggerJobsScrape,
    onSuccess: (data) => {
      alert(`Found ${data.scraped} new jobs`);
      qc.invalidateQueries({ queryKey: ["top-jobs"] });
    },
  });

  const enrichMut = useMutation({
    mutationFn: triggerEnrichEmails,
    onSuccess: (data) => {
      alert(`Enriched ${data.enriched} jobs with contact emails`);
      qc.invalidateQueries({ queryKey: ["top-jobs"] });
    },
  });

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-gray-100 px-8 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900 tracking-tight">AutoIntern</h1>
        <div className="flex gap-2">
          <button
            onClick={() => scrapeMut.mutate()}
            disabled={scrapeMut.isPending}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-gray-300 disabled:opacity-40 transition-colors"
          >
            {scrapeMut.isPending ? "Scraping…" : "Scrape YC"}
          </button>
          <button
            onClick={() => researchMut.mutate()}
            disabled={researchMut.isPending}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-gray-300 disabled:opacity-40 transition-colors"
          >
            {researchMut.isPending ? "Researching…" : "Research Batch"}
          </button>
          <button
            onClick={() => scrapeJobsMut.mutate()}
            disabled={scrapeJobsMut.isPending}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-gray-300 disabled:opacity-40 transition-colors"
          >
            {scrapeJobsMut.isPending ? "Scraping Jobs…" : "Scrape Jobs"}
          </button>
          <button
            onClick={() => enrichMut.mutate()}
            disabled={enrichMut.isPending}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-gray-300 disabled:opacity-40 transition-colors"
          >
            {enrichMut.isPending ? "Finding Emails…" : "Enrich Emails"}
          </button>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-8 py-8 space-y-10">
        <section>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-widest mb-4">
            Top Opportunities Today
          </h2>
          <OpportunityFeed />
        </section>

        <section>
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-widest mb-4">
            Applications
          </h2>
          <ApplicationTable />
        </section>
      </main>
    </div>
  );
}
