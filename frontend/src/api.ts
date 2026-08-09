import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000/api" });

export const getApplications = (status?: string) =>
  api.get("/applications", { params: { status } }).then((r) => r.data.applications);

export const getJobs = (params?: Record<string, unknown>) =>
  api.get("/jobs", { params }).then((r) => r.data.jobs);

export const getTopJobs = () =>
  api.get("/jobs/top").then((r) => r.data.top_jobs);

export const getApplication = (id: number) =>
  api.get(`/applications/${id}`).then((r) => r.data);

export const updateStatus = (id: number, status: string, notes?: string) =>
  api.patch(`/applications/${id}/status`, { status, notes }).then((r) => r.data);

export const generateApplication = (jobId: number) =>
  api.post(`/applications/generate/${jobId}`).then((r) => r.data);

export const triggerScrape = () =>
  api.post("/companies/scrape/yc").then((r) => r.data);

export const triggerResearch = () =>
  api.post("/companies/research/batch").then((r) => r.data);

export const triggerJobsScrape = () =>
  api.post("/jobs/scrape").then((r) => r.data);

export const triggerEnrichEmails = () =>
  api.post("/jobs/enrich-emails").then((r) => r.data);

export const sendApplication = (id: number) =>
  api.post(`/applications/${id}/send`).then((r) => r.data);

export default api;
