import { Loader2, Download, Clapperboard, Brain, Clock } from "lucide-react";
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
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-6">
      {error ? (
        <div className="text-center">
          <p className="text-sm font-medium text-red-400">Error</p>
          <p className="mt-1 text-sm text-red-300">{error}</p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3 text-emerald-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="flex items-center gap-2">
              {phase.icon}
              <span className="text-sm font-semibold">{phase.label}</span>
            </span>
          </div>

          <p className="mt-2 text-sm text-slate-400">{phase.description}</p>

          {/* Progress bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-500">Progress</span>
              <span className="font-mono text-xs text-slate-400">{pct}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
