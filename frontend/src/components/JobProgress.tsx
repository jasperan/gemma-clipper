import { Download, Clapperboard, Brain, Clock } from "lucide-react";
import type { JobStatus } from "../api/client";

interface Props {
  status: JobStatus;
  progress: number;
  error: string | null;
}

const PHASE_INFO: Record<
  string,
  { icon: React.ReactNode; label: string; description: string }
> = {
  pending: {
    icon: <Clock className="h-5 w-5" />,
    label: "Queued",
    description: "Waiting to start processing...",
  },
  downloading: {
    icon: <Download className="h-5 w-5" />,
    label: "Downloading",
    description: "Fetching video from source...",
  },
  processing: {
    icon: <Clapperboard className="h-5 w-5" />,
    label: "Processing",
    description: "Detecting scenes and extracting frames...",
  },
  analyzing: {
    icon: <Brain className="h-5 w-5" />,
    label: "Analyzing",
    description: "AI is scoring scenes for interest...",
  },
};

export default function JobProgress({ status, progress, error }: Props) {
  if (status === "complete" || status === "failed") return null;

  const phase = PHASE_INFO[status] ?? PHASE_INFO.pending;
  const pct = Math.min(100, Math.max(0, progress));

  return (
    <div className="rounded-2xl border border-border bg-surface-raised p-6 shadow-card" role="status" aria-live="polite">
      {error ? (
        <div className="text-center">
          <p className="text-sm font-semibold text-red-400">Error</p>
          <p className="mt-1.5 text-sm text-red-300/80">{error}</p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3">
            {/* Animated phase icon */}
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-muted text-accent">
              {phase.icon}
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-200">{phase.label}</p>
              <p className="text-xs text-zinc-500">{phase.description}</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-zinc-500">Progress</span>
              <span className="font-mono text-xs tabular-nums text-zinc-400">{pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-surface-overlay">
              <div
                className="h-full rounded-full bg-accent transition-all duration-700 ease-out"
                style={{
                  width: `${pct}%`,
                  boxShadow: pct > 0 ? "0 0 12px rgba(52, 211, 153, 0.3)" : "none",
                }}
              />
            </div>
          </div>

          {/* Skeleton preview: shows expected layout shape */}
          <div className="mt-5 grid grid-cols-3 gap-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2 animate-pulse" style={{ animationDelay: `${i * 150}ms` }}>
                <div className="aspect-video rounded-lg bg-surface-overlay" />
                <div className="h-2 w-3/4 rounded bg-surface-overlay" />
                <div className="h-2 w-1/2 rounded bg-surface-overlay" />
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
