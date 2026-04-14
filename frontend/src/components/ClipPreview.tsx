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
      <div className="flex flex-col items-center justify-center py-16 text-zinc-600">
        <Scissors className="mb-3 h-10 w-10" />
        <p className="text-sm font-medium">No clips generated yet</p>
        <p className="mt-1 text-xs text-zinc-700">Clips will appear here after processing</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {clips.map((clip, idx) => (
        <article
          key={clip.id}
          className="rounded-2xl bg-surface-raised shadow-card overflow-hidden transition-all duration-300 hover:shadow-card-hover animate-fade-in"
          style={{ animationDelay: `${idx * 60}ms` }}
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
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="inline-flex items-center justify-center h-5 min-w-[1.5rem] rounded-md bg-surface-overlay font-mono text-[10px] font-semibold tabular-nums text-zinc-400">
                    {idx + 1}
                  </span>
                  <span className="font-mono text-xs tabular-nums text-zinc-500">
                    {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
                  </span>
                  <span className="font-mono text-[10px] tabular-nums text-zinc-600">
                    ({clip.duration.toFixed(1)}s)
                  </span>
                </div>
                {clip.reason && (
                  <p className="mt-1 text-sm leading-relaxed text-zinc-300 text-pretty">{clip.reason}</p>
                )}
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {/* Score */}
                <div className="flex items-center gap-1 rounded-lg bg-amber-400/8 ring-1 ring-amber-400/15 px-2.5 py-1">
                  <Star className="h-3 w-3 text-amber-400" />
                  <span className="font-mono text-xs font-semibold tabular-nums text-amber-400">
                    {(clip.interest_score * 10).toFixed(1)}
                  </span>
                </div>

                {/* Download */}
                {clip.exported_path ? (
                  <a
                    href={clipDownloadUrl(clip.id)}
                    download
                    className="focus-ring rounded-lg bg-accent p-2 text-[#0c0c0e] hover:bg-accent-dim active:scale-95 transition-all duration-200"
                    title="Download clip"
                    aria-label={`Download clip ${idx + 1}`}
                  >
                    <Download className="h-4 w-4" />
                  </a>
                ) : (
                  <span
                    className="rounded-lg bg-surface-overlay p-2 text-zinc-600"
                    title="Not yet exported"
                  >
                    <Play className="h-4 w-4" />
                  </span>
                )}
              </div>
            </div>

            {/* Interest score bar */}
            <div className="mt-3.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-overlay">
              <div
                className="h-full rounded-full bg-accent/50 transition-all duration-500"
                style={{
                  width: `${Math.min(100, clip.interest_score * 100)}%`,
                }}
              />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
