import { Film, Trash2, Loader2 } from "lucide-react";
import { useJobs, useDeleteJob } from "../hooks/useJobs";
import type { JobStatus } from "../api/client";

interface Props {
  selectedJobId: string | null;
  onSelect: (id: string) => void;
}

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: "bg-slate-500",
  downloading: "bg-blue-500",
  processing: "bg-amber-500",
  analyzing: "bg-purple-500",
  complete: "bg-emerald-500",
  failed: "bg-red-500",
};

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pending",
  downloading: "Downloading",
  processing: "Processing",
  analyzing: "Analyzing",
  complete: "Complete",
  failed: "Failed",
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function JobList({ selectedJobId, onSelect }: Props) {
  const { data: jobs, isLoading, error } = useJobs();
  const deleteMut = useDeleteJob();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-slate-500" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="px-3 py-6 text-center text-sm text-slate-500">
        Could not load jobs
      </p>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500">
        <Film className="mb-2 h-8 w-8" />
        <p className="text-sm">No jobs yet</p>
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {jobs.map((job) => {
        const active = job.id === selectedJobId;
        const isRunning = ["pending", "downloading", "processing", "analyzing"].includes(job.status);

        return (
          <li key={job.id}>
            <button
              onClick={() => onSelect(job.id)}
              className={`group w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                active
                  ? "bg-slate-700/80"
                  : "hover:bg-slate-800/60"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">
                    {job.source_name || job.id.slice(0, 8)}
                  </p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="flex items-center gap-1.5">
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_COLORS[job.status]} ${
                          isRunning ? "animate-pulse" : ""
                        }`}
                      />
                      <span className="text-xs text-slate-400">
                        {STATUS_LABELS[job.status]}
                      </span>
                    </span>
                    {job.clips_generated > 0 && (
                      <span className="text-xs text-slate-500">
                        {job.clips_generated} clip{job.clips_generated !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-[10px] text-slate-500">
                    {timeAgo(job.created_at)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this job?")) {
                        deleteMut.mutate(job.id);
                      }
                    }}
                    className="rounded p-1 text-slate-600 opacity-0 transition-opacity hover:bg-slate-700 hover:text-red-400 group-hover:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
