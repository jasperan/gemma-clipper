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
const CAPTION_STYLES = ["default", "bold", "outline", "shadow"];

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
    <div className="rounded-xl border border-slate-700 bg-slate-800/60 p-4 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
        <Download className="h-4 w-4 text-emerald-400" />
        Export
      </h3>

      {/* Format */}
      <div>
        <label className="mb-1.5 flex items-center gap-1.5 text-xs text-slate-400">
          <FileVideo className="h-3 w-3" /> Format
        </label>
        <div className="flex gap-1.5">
          {FORMATS.map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium uppercase transition-colors ${
                format === f
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Aspect ratio */}
      <div>
        <label className="mb-1.5 flex items-center gap-1.5 text-xs text-slate-400">
          <Ratio className="h-3 w-3" /> Aspect ratio
        </label>
        <div className="flex flex-wrap gap-1.5">
          {ASPECT_RATIOS.map((ar) => (
            <button
              key={ar.value}
              onClick={() => setAspectRatio(ar.value)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                aspectRatio === ar.value
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              {ar.label}
            </button>
          ))}
        </div>
      </div>

      {/* Captions */}
      <div className="space-y-2">
        <label className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <Type className="h-3 w-3" /> Captions
          </span>
          <button
            onClick={() => setAddCaptions((v) => !v)}
            className={`relative h-5 w-9 rounded-full transition-colors ${
              addCaptions ? "bg-emerald-500" : "bg-slate-600"
            }`}
          >
            <span
              className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                addCaptions ? "left-[18px]" : "left-0.5"
              }`}
            />
          </button>
        </label>
        {addCaptions && (
          <div className="flex gap-1.5">
            {CAPTION_STYLES.map((s) => (
              <button
                key={s}
                onClick={() => setCaptionStyle(s)}
                className={`rounded-lg px-2.5 py-1 text-[11px] capitalize transition-colors ${
                  captionStyle === s
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-700 text-slate-400 hover:text-slate-200"
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
        <div className="flex items-center justify-between mb-1">
          <span className="flex items-center gap-1.5 text-xs text-slate-400">
            <Gauge className="h-3 w-3" /> Quality (CRF)
          </span>
          <span className="font-mono text-xs text-slate-400">{crf}</span>
        </div>
        <input
          type="range"
          min={15}
          max={35}
          value={crf}
          onChange={(e) => setCrf(Number(e.target.value))}
          className="w-full accent-emerald-500"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>Higher quality</span>
          <span>Smaller file</span>
        </div>
      </div>

      {/* Max width */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-slate-400">Max width</span>
          <span className="font-mono text-xs text-slate-400">{maxWidth}px</span>
        </div>
        <input
          type="range"
          min={480}
          max={3840}
          step={160}
          value={maxWidth}
          onChange={(e) => setMaxWidth(Number(e.target.value))}
          className="w-full accent-emerald-500"
        />
      </div>

      {/* Export buttons */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => doExport(selectedClipIds)}
          disabled={exportMut.isPending || selectedClipIds.length === 0}
          className="flex-1 rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white
                     hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors flex items-center justify-center gap-2"
        >
          {exportMut.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {selectedSceneIds.size > 0
            ? `Export Selected (${selectedClipIds.length})`
            : "Export All"}
        </button>
      </div>

      {exportMut.error && (
        <p className="text-xs text-red-400">
          {(exportMut.error as Error).message}
        </p>
      )}
    </div>
  );
}
