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
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.4) return "bg-amber-500";
  return "bg-red-500";
}

function scoreBorder(score: number): string {
  if (score >= 0.7) return "border-emerald-500/30";
  if (score >= 0.4) return "border-amber-500/30";
  return "border-red-500/30";
}

export default function SceneList({ scenes, selectedIds, onToggle }: Props) {
  if (scenes.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No scenes detected yet
      </p>
    );
  }

  const sorted = [...scenes].sort(
    (a, b) => b.interest_score - a.interest_score,
  );

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {sorted.map((scene) => {
        const selected = selectedIds.has(scene.id);
        return (
          <button
            key={scene.id}
            onClick={() => onToggle(scene.id)}
            className={`group relative rounded-xl border text-left transition-all duration-200
              ${
                selected
                  ? "border-emerald-500/50 bg-emerald-500/10 ring-1 ring-emerald-500/30"
                  : `${scoreBorder(scene.interest_score)} bg-slate-800/60 hover:bg-slate-800`
              }
            `}
          >
            {/* Thumbnail */}
            <div className="relative aspect-video w-full overflow-hidden rounded-t-xl bg-slate-700">
              {scene.thumbnail_path ? (
                <img
                  src={scene.thumbnail_path}
                  alt={scene.description || "Scene thumbnail"}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <Image className="h-8 w-8 text-slate-600" />
                </div>
              )}

              {/* Time overlay */}
              <div className="absolute bottom-2 left-2 flex items-center gap-1.5">
                <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-white backdrop-blur-sm">
                  {formatTime(scene.start_time)}
                </span>
                <span className="text-[10px] text-white/60">-</span>
                <span className="rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-white backdrop-blur-sm">
                  {formatTime(scene.end_time)}
                </span>
              </div>

              {/* Duration badge */}
              <span className="absolute right-2 top-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[10px] text-white backdrop-blur-sm">
                {scene.duration.toFixed(1)}s
              </span>

              {/* Selection indicator */}
              {selected && (
                <div className="absolute inset-0 flex items-center justify-center bg-emerald-500/20">
                  <div className="rounded-full bg-emerald-500 p-1">
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              )}
            </div>

            {/* Content */}
            <div className="p-3">
              {/* Score bar */}
              <div className="mb-2 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-700">
                  <div
                    className={`h-full rounded-full ${scoreColor(scene.interest_score)} transition-all`}
                    style={{
                      width: `${Math.round(scene.interest_score * 100)}%`,
                    }}
                  />
                </div>
                <span className="font-mono text-xs font-semibold text-amber-400">
                  {(scene.interest_score * 10).toFixed(1)}
                </span>
              </div>

              {/* Description */}
              {scene.description && (
                <p className="mb-2 line-clamp-2 text-xs text-slate-300">
                  {scene.description}
                </p>
              )}

              {/* Tags + audio indicators */}
              <div className="flex flex-wrap items-center gap-1.5">
                {scene.tags?.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-0.5 rounded-full bg-slate-700 px-2 py-0.5 text-[10px] text-slate-400"
                  >
                    <Tag className="h-2.5 w-2.5" />
                    {tag}
                  </span>
                ))}
                {scene.has_speech && (
                  <span title="Has speech"><Mic className="h-3 w-3 text-blue-400" /></span>
                )}
                {scene.has_music && (
                  <span title="Has music"><Music className="h-3 w-3 text-purple-400" /></span>
                )}
                {scene.is_silent && (
                  <span title="Silent"><VolumeX className="h-3 w-3 text-slate-500" /></span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
