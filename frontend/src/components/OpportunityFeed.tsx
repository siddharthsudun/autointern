import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTopJobs, generateApplication } from "../api";

export default function OpportunityFeed() {
  const qc = useQueryClient();
  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["top-jobs"],
    queryFn: getTopJobs,
  });

  const applyMut = useMutation({
    mutationFn: (jobId: number) => generateApplication(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  if (isLoading) return <p className="text-gray-400 text-sm">Loading opportunities…</p>;

  return (
    <div className="space-y-2">
      {jobs.map((job: any) => (
        <div
          key={job.id}
          className="flex items-center justify-between px-4 py-3 rounded-xl border border-gray-100 hover:border-gray-200 transition-colors"
        >
          <div className="flex items-center gap-3 min-w-0">
            {job.company_logo && (
              <img
                src={job.company_logo}
                alt=""
                className="w-8 h-8 rounded-lg object-contain bg-gray-50 flex-shrink-0"
              />
            )}
            <div className="min-w-0">
              <p className="font-medium text-gray-900 truncate">{job.title}</p>
              <p className="text-xs text-gray-400">
                {job.company_name}
                {job.yc_batch && (
                  <span className="ml-1.5 bg-orange-50 text-orange-600 rounded px-1 py-0.5 text-[10px] font-medium">
                    YC {job.yc_batch}
                  </span>
                )}
                {job.location && <span className="ml-2">{job.location}</span>}
              {job.apply_email && (
                <span className="ml-2 text-green-600" title={job.apply_email}>✉</span>
              )}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            {job.match_score != null && (
              <span className="text-xs font-medium text-gray-500">
                {Math.round(job.match_score)}% match
              </span>
            )}
            <button
              onClick={() => applyMut.mutate(job.id)}
              disabled={applyMut.isPending}
              className="text-xs px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition-colors"
            >
              Generate
            </button>
            {job.apply_url && (
              <a
                href={job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                ↗
              </a>
            )}
          </div>
        </div>
      ))}
      {jobs.length === 0 && (
        <p className="text-gray-400 text-sm py-4">
          No scored opportunities yet. Run the daily pipeline to discover and score jobs.
        </p>
      )}
    </div>
  );
}
