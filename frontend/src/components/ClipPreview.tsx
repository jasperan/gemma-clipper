import { Play, Download, Scissors, Star } from "lucide-react";
import { clipDownloadUrl, type Clip } from "../api/client";

interface Props {
  clips: Clip[];
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ClipPreview({ clips }: Props) {
  if (clips.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500">
        <Scissors className="mb-2 h-8 w-8" />
        <p className="text-sm">No clips generated yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {clips.map((clip, idx) => (
        <div
          key={clip.id}
          className="rounded-xl border border-slate-700 bg-slate-800/60 overflow-hidden"
        >
          {/* Video player for exported clips */}
          {clip.exported_path && (
            <div className="relative aspect-video w-full bg-black">
              <video
                src={clip.exported_path}
                controls
                preload="metadata"
                poster={clip.thumbnail_path ?? undefined}
                className="h-full w-full"
              />
            </div>
          )}

          {/* Clip info */}
          <div className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="rounded bg-slate-700 px-2 py-0.5 text-xs font-medium text-slate-300">
                    #{idx + 1}
                  </span>
                  <span className="font-mono text-xs text-slate-400">
                    {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
                  </span>
                  <span className="font-mono text-xs text-slate-500">
                    ({clip.duration.toFixed(1)}s)
                  </span>
                </div>
                {clip.reason && (
                  <p className="mt-1 text-sm text-slate-300">{clip.reason}</p>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {/* Score */}
                <div className="flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-1">
                  <Star className="h-3 w-3 text-amber-400" />
                  <span className="font-mono text-xs font-semibold text-amber-400">
                    {(clip.interest_score * 10).toFixed(1)}
                  </span>
                </div>

                {/* Download */}
                {clip.exported_path ? (
                  <a
                    href={clipDownloadUrl(clip.id)}
                    download
                    className="rounded-lg bg-emerald-600 p-2 text-white hover:bg-emerald-500 transition-colors"
                    title="Download clip"
                  >
                    <Download className="h-4 w-4" />
                  </a>
                ) : (
                  <span
                    className="rounded-lg bg-slate-700 p-2 text-slate-500"
                    title="Not yet exported"
                  >
                    <Play className="h-4 w-4" />
                  </span>
                )}
              </div>
            </div>

            {/* Timeline bar */}
            <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-emerald-500/60"
                style={{
                  width: `${Math.min(100, clip.interest_score * 100)}%`,
                }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
