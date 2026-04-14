import { Image, Tag, Mic, Music, VolumeX } from "lucide-react";
import type { Scene } from "../api/client";

interface Props {
  scenes: Scene[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
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

function scoreColor(score: number): string {
  if (score >= 0.7) return "bg-accent";
  if (score >= 0.4) return "bg-amber-400";
  return "bg-red-400";
}

function scoreRingColor(score: number): string {
  if (score >= 0.7) return "ring-accent/20";
  if (score >= 0.4) return "ring-amber-400/20";
  return "ring-red-400/20";
}

export default function SceneList({ scenes, selectedIds, onToggle }: Props) {
  if (scenes.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500">
        No scenes detected yet
      </p>
    );
  }

  const sorted = [...scenes].sort(
    (a, b) => b.interest_score - a.interest_score,
  );

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {sorted.map((scene, idx) => {
        const selected = selectedIds.has(scene.id);
        return (
          <button
            key={scene.id}
            onClick={() => onToggle(scene.id)}
            className={`focus-ring group relative rounded-2xl text-left transition-all duration-250 animate-fade-in overflow-hidden
              ${
                selected
                  ? "ring-2 ring-accent/40 shadow-glow bg-surface-raised"
                  : `bg-surface-raised shadow-card hover:shadow-card-hover hover:-translate-y-0.5`
              }
            `}
            style={{ animationDelay: `${idx * 40}ms` }}
            aria-pressed={selected}
            aria-label={`Scene at ${formatTime(scene.start_time)}, score ${(scene.interest_score * 10).toFixed(1)}`}
          >
            {/* Thumbnail */}
            <div className="relative aspect-video w-full overflow-hidden bg-surface-overlay">
              {scene.thumbnail_path ? (
                <img
                  src={scene.thumbnail_path}
                  alt={scene.description || "Scene thumbnail"}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Image className="h-8 w-8 text-zinc-700" />
                </div>
              )}

              {/* Gradient overlay at bottom */}
              <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-black/60 to-transparent" />

              {/* Time overlay */}
              <div className="absolute bottom-2 left-2 flex items-center gap-1">
                <span className="rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-white backdrop-blur-sm">
                  {formatTime(scene.start_time)}
                </span>
                <span className="text-[10px] text-white/50">/</span>
                <span className="rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-white backdrop-blur-sm">
                  {formatTime(scene.end_time)}
                </span>
              </div>

              {/* Duration badge */}
              <span className="absolute right-2 top-2 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-white backdrop-blur-sm">
                {scene.duration.toFixed(1)}s
              </span>

              {/* Selection indicator */}
              {selected && (
                <div className="absolute inset-0 flex items-center justify-center bg-accent/15 backdrop-blur-[1px]">
                  <div className="rounded-full bg-accent p-1.5 shadow-glow">
                    <svg className="h-4 w-4 text-[#0c0c0e]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              )}
            </div>

            {/* Content */}
            <div className="p-3.5">
              {/* Score bar */}
              <div className="mb-2.5 flex items-center gap-2.5">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-overlay">
                  <div
                    className={`h-full rounded-full ${scoreColor(scene.interest_score)} transition-all duration-500`}
                    style={{
                      width: `${Math.round(scene.interest_score * 100)}%`,
                    }}
                  />
                </div>
                <span className={`inline-flex items-center justify-center h-6 min-w-[2.25rem] rounded-md ring-1 ${scoreRingColor(scene.interest_score)} font-mono text-[11px] font-semibold tabular-nums text-amber-400`}>
                  {(scene.interest_score * 10).toFixed(1)}
                </span>
              </div>

              {/* Description */}
              {scene.description && (
                <p className="mb-2.5 line-clamp-2 text-xs leading-relaxed text-zinc-400 text-pretty">
                  {scene.description}
                </p>
              )}

              {/* Tags + audio indicators */}
              <div className="flex flex-wrap items-center gap-1.5">
                {scene.tags?.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-0.5 rounded-md bg-surface-overlay px-2 py-0.5 text-[10px] font-medium text-zinc-500"
                  >
                    <Tag className="h-2.5 w-2.5" />
                    {tag}
                  </span>
                ))}
                {scene.has_speech && (
                  <span title="Has speech" className="rounded-md bg-blue-400/10 p-1">
                    <Mic className="h-3 w-3 text-blue-400" />
                  </span>
                )}
                {scene.has_music && (
                  <span title="Has music" className="rounded-md bg-violet-400/10 p-1">
                    <Music className="h-3 w-3 text-violet-400" />
                  </span>
                )}
                {scene.is_silent && (
                  <span title="Silent" className="rounded-md bg-surface-overlay p-1">
                    <VolumeX className="h-3 w-3 text-zinc-600" />
                  </span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
