import { Film, Trash2, Loader2 } from "lucide-react";
import { useJobs, useDeleteJob } from "../hooks/useJobs";
import type { JobStatus } from "../api/client";

interface Props {
  selectedJobId: string | null;
  onSelect: (id: string) => void;
}

const STATUS_COLORS: Record<JobStatus, string> = {
  pending: "bg-zinc-500",
  downloading: "bg-blue-400",
  processing: "bg-amber-400",
  analyzing: "bg-violet-400",
  complete: "bg-accent",
  failed: "bg-red-400",
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
        <Loader2 className="h-5 w-5 animate-spin text-zinc-600" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="px-3 py-6 text-center text-sm text-zinc-500" role="alert">
        Could not load jobs
      </p>
    );
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-zinc-600">
        <Film className="mb-2 h-8 w-8" />
        <p className="text-sm">No jobs yet</p>
      </div>
    );
  }

  return (
    <ul className="space-y-0.5" role="listbox" aria-label="Processing jobs">
      {jobs.map((job) => {
        const active = job.id === selectedJobId;
        const isRunning = ["pending", "downloading", "processing", "analyzing"].includes(job.status);

        return (
          <li key={job.id} role="option" aria-selected={active}>
            <button
              onClick={() => onSelect(job.id)}
              className={`focus-ring group w-full rounded-lg px-3 py-2.5 text-left transition-all duration-200 ${
                active
                  ? "bg-surface-overlay shadow-card"
                  : "hover:bg-surface-overlay/50"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-200">
                    {job.source_name || job.id.slice(0, 8)}
                  </p>
                  <div className="mt-1 flex items-center gap-2.5">
                    <span className="flex items-center gap-1.5">
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${STATUS_COLORS[job.status]} ${
                          isRunning ? "animate-pulse-slow" : ""
                        }`}
                      />
                      <span className="text-xs text-zinc-500">
                        {STATUS_LABELS[job.status]}
                      </span>
                    </span>
                    {job.clips_generated > 0 && (
                      <span className="font-mono text-xs tabular-nums text-zinc-600">
                        {job.clips_generated} clip{job.clips_generated !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span className="font-mono text-[10px] tabular-nums text-zinc-600">
                    {timeAgo(job.created_at)}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("Delete this job?")) {
                        deleteMut.mutate(job.id);
                      }
                    }}
                    className="focus-ring rounded-md p-1 text-zinc-700 opacity-0 transition-all duration-200 hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100 active:scale-90"
                    aria-label={`Delete job ${job.source_name || job.id.slice(0, 8)}`}
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
