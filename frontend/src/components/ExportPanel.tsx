import { useState } from "react";
import { Download, Loader2, FileVideo, Ratio, Type, Gauge } from "lucide-react";
import { useExportClips } from "../hooks/useJobs";
import type { Clip } from "../api/client";

interface Props {
  jobId: string;
  clips: Clip[];
  selectedSceneIds: Set<string>;
}

const FORMATS = ["mp4", "webm", "gif"] as const;
const ASPECT_RATIOS = [
  { value: "original", label: "Original" },
  { value: "16:9", label: "16:9" },
  { value: "9:16", label: "9:16" },
  { value: "1:1", label: "1:1" },
];
const CAPTION_STYLES = ["default", "bold", "minimal"];

export default function ExportPanel({ jobId, clips, selectedSceneIds }: Props) {
  const [format, setFormat] = useState<string>("mp4");
  const [aspectRatio, setAspectRatio] = useState("original");
  const [addCaptions, setAddCaptions] = useState(false);
  const [captionStyle, setCaptionStyle] = useState("default");
  const [crf, setCrf] = useState(23);
  const [maxWidth, setMaxWidth] = useState(1920);

  const exportMut = useExportClips();

  const selectedClipIds = clips
    .filter((c) => {
      if (selectedSceneIds.size === 0) return true;
      return c.source_scene_ids?.some((sid) => selectedSceneIds.has(sid));
    })
    .map((c) => c.id);

  const doExport = (clipIds: string[]) => {
    if (clipIds.length === 0) return;
    exportMut.mutate({
      jobId,
      options: {
        clip_ids: clipIds,
        format,
        aspect_ratio: aspectRatio,
        add_captions: addCaptions,
        caption_style: captionStyle,
        crf,
        max_width: maxWidth,
      },
    });
  };

  return (
    <section className="rounded-2xl border border-border bg-surface-raised p-4 space-y-4 shadow-card" aria-label="Export options">
      <h3 className="text-sm font-semibold text-zinc-200 flex items-center gap-2.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent-muted">
          <Download className="h-3.5 w-3.5 text-accent" />
        </div>
        Export
      </h3>

      {/* Format */}
      <fieldset>
        <legend className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
          <FileVideo className="h-3 w-3" /> Format
        </legend>
        <div className="flex gap-1.5">
          {FORMATS.map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={`focus-ring rounded-lg px-3 py-1.5 text-xs font-semibold uppercase transition-all duration-200 ${
                format === f
                  ? "bg-accent text-[#0c0c0e] shadow-glow"
                  : "bg-surface-overlay text-zinc-500 hover:text-zinc-300 hover:bg-border"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Aspect ratio */}
      <fieldset>
        <legend className="mb-2 flex items-center gap-1.5 text-xs font-medium text-zinc-500">
          <Ratio className="h-3 w-3" /> Aspect ratio
        </legend>
        <div className="flex flex-wrap gap-1.5">
          {ASPECT_RATIOS.map((ar) => (
            <button
              key={ar.value}
              onClick={() => setAspectRatio(ar.value)}
              className={`focus-ring rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                aspectRatio === ar.value
                  ? "bg-accent text-[#0c0c0e]"
                  : "bg-surface-overlay text-zinc-500 hover:text-zinc-300 hover:bg-border"
              }`}
            >
              {ar.label}
            </button>
          ))}
        </div>
      </fieldset>

      {/* Captions */}
      <div className="space-y-2.5">
        <label className="flex items-center justify-between cursor-pointer group">
          <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 group-hover:text-zinc-400 transition-colors">
            <Type className="h-3 w-3" /> Captions
          </span>
          <button
            onClick={() => setAddCaptions((v) => !v)}
            role="switch"
            aria-checked={addCaptions}
            className={`focus-ring relative h-5 w-9 rounded-full transition-colors duration-200 ${
              addCaptions ? "bg-accent" : "bg-border-active"
            }`}
          >
            <span
              className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200 ${
                addCaptions ? "left-[18px]" : "left-0.5"
              }`}
            />
          </button>
        </label>
        {addCaptions && (
          <div className="flex gap-1.5 animate-fade-in">
            {CAPTION_STYLES.map((s) => (
              <button
                key={s}
                onClick={() => setCaptionStyle(s)}
                className={`focus-ring rounded-lg px-2.5 py-1 text-[11px] font-medium capitalize transition-all duration-200 ${
                  captionStyle === s
                    ? "bg-accent text-[#0c0c0e]"
                    : "bg-surface-overlay text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Quality (CRF) */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="flex items-center gap-1.5 text-xs font-medium text-zinc-500">
            <Gauge className="h-3 w-3" /> Quality (CRF)
          </span>
          <span className="font-mono text-xs tabular-nums text-zinc-400">{crf}</span>
        </div>
        <input
          type="range"
          min={15}
          max={35}
          value={crf}
          onChange={(e) => setCrf(Number(e.target.value))}
          className="w-full accent-accent"
          aria-label="Video quality CRF value"
        />
        <div className="flex justify-between mt-1 text-[10px] text-zinc-600">
          <span>Higher quality</span>
          <span>Smaller file</span>
        </div>
      </div>

      {/* Max width */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-zinc-500">Max width</span>
          <span className="font-mono text-xs tabular-nums text-zinc-400">{maxWidth}px</span>
        </div>
        <input
          type="range"
          min={480}
          max={3840}
          step={160}
          value={maxWidth}
          onChange={(e) => setMaxWidth(Number(e.target.value))}
          className="w-full accent-accent"
          aria-label="Maximum output width in pixels"
        />
      </div>

      {/* Export button */}
      <div className="pt-1">
        <button
          onClick={() => doExport(selectedClipIds)}
          disabled={exportMut.isPending || selectedClipIds.length === 0}
          className="focus-ring w-full rounded-xl bg-accent py-3 text-sm font-semibold text-[#0c0c0e]
                     hover:bg-accent-dim active:scale-[0.98]
                     disabled:opacity-30 disabled:cursor-not-allowed
                     transition-all duration-200 flex items-center justify-center gap-2
                     shadow-glow"
        >
          {exportMut.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {selectedSceneIds.size > 0
            ? `Export selected (${selectedClipIds.length})`
            : "Export all"}
        </button>
      </div>

      {exportMut.error && (
        <p className="text-xs text-red-400 animate-fade-in" role="alert">
          {(exportMut.error as Error).message}
        </p>
      )}
    </section>
  );
}
