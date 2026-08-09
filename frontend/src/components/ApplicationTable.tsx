import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getApplications, updateStatus, sendApplication } from "../api";
import StatusBadge from "./StatusBadge";
import { format } from "date-fns";

const STATUSES = [
  "draft", "pending_review", "approved", "sent",
  "acknowledged", "interviewing", "rejected", "ghosted", "offer",
];

export default function ApplicationTable() {
  const qc = useQueryClient();
  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["applications"],
    queryFn: () => getApplications(),
  });

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });

  const sendMut = useMutation({
    mutationFn: (id: number) => sendApplication(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
    onError: (e: any) => alert(e?.response?.data?.detail ?? "Send failed"),
  });

  if (isLoading) return <p className="text-gray-400 text-sm">Loading…</p>;

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-100">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
            <th className="px-4 py-3 font-medium">Company</th>
            <th className="px-4 py-3 font-medium">Role</th>
            <th className="px-4 py-3 font-medium">Method</th>
            <th className="px-4 py-3 font-medium">Date</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app: any) => (
            <tr key={app.id} className="border-b border-gray-50 hover:bg-gray-50/50 transition-colors">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {app.company_logo && (
                    <img
                      src={app.company_logo}
                      alt=""
                      className="w-6 h-6 rounded object-contain bg-gray-50"
                    />
                  )}
                  <span className="font-medium text-gray-900">{app.company_name}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-gray-600">{app.job_title}</td>
              <td className="px-4 py-3 text-gray-500">{app.sent_via ?? "—"}</td>
              <td className="px-4 py-3 text-gray-400">
                {app.sent_at
                  ? format(new Date(app.sent_at), "MMM d")
                  : format(new Date(app.created_at), "MMM d")}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={app.status} />
              </td>
              <td className="px-4 py-3 flex items-center gap-2">
                <select
                  value={app.status}
                  onChange={(e) => statusMut.mutate({ id: app.id, status: e.target.value })}
                  className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white text-gray-600 focus:outline-none focus:ring-1 focus:ring-gray-300"
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                  ))}
                </select>
                {app.status === "approved" && (
                  <button
                    onClick={() => sendMut.mutate(app.id)}
                    disabled={sendMut.isPending}
                    className="text-xs px-2 py-1 rounded bg-gray-900 text-white hover:bg-gray-700 disabled:opacity-40 transition-colors"
                  >
                    Send
                  </button>
                )}
              </td>
            </tr>
          ))}
          {apps.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                No applications yet. Discover jobs → generate applications to get started.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
