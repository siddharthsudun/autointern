import clsx from "clsx";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  pending_review: "bg-yellow-100 text-yellow-700",
  approved: "bg-blue-100 text-blue-700",
  sent: "bg-indigo-100 text-indigo-700",
  acknowledged: "bg-purple-100 text-purple-700",
  interviewing: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-600",
  ghosted: "bg-gray-100 text-gray-500",
  offer: "bg-emerald-100 text-emerald-700",
};

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        "inline-block px-2 py-0.5 rounded text-xs font-medium tracking-wide",
        STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600"
      )}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
