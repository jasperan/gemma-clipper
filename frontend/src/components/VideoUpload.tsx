import { useState, useRef, useCallback } from "react";
import { Upload, Youtube, Settings2, Loader2, AlertCircle } from "lucide-react";
import { useCreateUploadJob, useCreateYouTubeJob } from "../hooks/useJobs";

interface Props {
  onJobCreated: (jobId: string) => void;
}

export default function VideoUpload({ onJobCreated }: Props) {
  // Input state
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Options
  const [autoClip, setAutoClip] = useState(true);
  const [maxClips, setMaxClips] = useState(10);
  const [minDuration, setMinDuration] = useState(3);
  const [maxDuration, setMaxDuration] = useState(60);
  const [showOptions, setShowOptions] = useState(false);

  const uploadMut = useCreateUploadJob();
  const ytMut = useCreateYouTubeJob();

  const options = {
    auto_clip: autoClip,
    max_clips: maxClips,
    min_clip_duration: minDuration,
    max_clip_duration: maxDuration,
  };

  const busy = uploadMut.isPending || ytMut.isPending;

  // ---- File upload --------------------------------------------------------

  const handleFile = useCallback(
    (file: File) => {
      if (busy) return;
      setUploadPct(0);
      uploadMut.mutate(
        { file, options, onProgress: (p) => setUploadPct(p) },
        {
          onSuccess: (job) => {
            setUploadPct(null);
            onJobCreated(job.id);
          },
          onError: () => setUploadPct(null),
        },
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, options],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  // ---- YouTube ------------------------------------------------------------

  const submitYouTube = () => {
    if (!youtubeUrl.trim() || busy) return;
    ytMut.mutate(
      { url: youtubeUrl.trim(), options },
      {
        onSuccess: (job) => {
          setYoutubeUrl("");
          onJobCreated(job.id);
        },
      },
    );
  };

  const error = uploadMut.error || ytMut.error;

  return (
    <div className="space-y-3.5">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !busy && fileRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            !busy && fileRef.current?.click();
          }
        }}
        className={`
          focus-ring relative cursor-pointer rounded-xl border-2 border-dashed
          transition-all duration-250 p-6 text-center group
          ${
            dragOver
              ? "border-accent bg-accent-muted scale-[1.01]"
              : "border-border-hover hover:border-zinc-500 bg-surface-overlay/50 hover:bg-surface-overlay"
          }
          ${busy ? "pointer-events-none opacity-50" : ""}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={onFileChange}
          aria-label="Upload video file"
        />
        <div className="flex h-10 w-10 mx-auto mb-3 items-center justify-center rounded-lg bg-surface-overlay transition-colors group-hover:bg-border">
          <Upload className="h-5 w-5 text-zinc-400 transition-transform group-hover:-translate-y-0.5" />
        </div>
        <p className="text-sm font-medium text-zinc-300">
          Drop a video here or click to browse
        </p>
        <p className="mt-1 text-xs text-zinc-500">
          MP4, MOV, AVI, MKV, WebM
        </p>

        {uploadPct !== null && (
          <div className="mt-4 animate-fade-in">
            <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
              <div
                className="h-full rounded-full bg-accent transition-all duration-300 ease-out"
                style={{ width: `${uploadPct}%` }}
              />
            </div>
            <p className="mt-1.5 font-mono text-xs tabular-nums text-zinc-400">{uploadPct}% uploaded</p>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-[10px] text-zinc-600 uppercase tracking-widest font-medium">
          or
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* YouTube input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Youtube className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-600" />
          <input
            type="url"
            placeholder="Paste YouTube URL..."
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitYouTube()}
            className="focus-ring w-full rounded-lg border border-border bg-surface-overlay py-2.5 pl-10 pr-3
                       text-sm text-zinc-200 placeholder-zinc-600
                       focus:border-accent/50 focus:outline-none
                       transition-colors duration-200"
          />
        </div>
        <button
          onClick={submitYouTube}
          disabled={busy || !youtubeUrl.trim()}
          className="focus-ring rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-[#0c0c0e]
                     hover:bg-accent-dim active:scale-[0.97]
                     disabled:opacity-30 disabled:cursor-not-allowed
                     transition-all duration-200"
        >
          {ytMut.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            "Clip"
          )}
        </button>
      </div>

      {/* Options toggle */}
      <button
        onClick={() => setShowOptions((v) => !v)}
        className="focus-ring flex items-center gap-1.5 rounded-md px-1 py-0.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors duration-200"
      >
        <Settings2 className={`h-3.5 w-3.5 transition-transform duration-200 ${showOptions ? "rotate-90" : ""}`} />
        {showOptions ? "Hide options" : "Clipping options"}
      </button>

      {showOptions && (
        <div className="space-y-3 rounded-xl border border-border bg-surface-overlay p-4 animate-slide-up">
          {/* Auto-clip toggle */}
          <label className="flex items-center justify-between cursor-pointer group">
            <span className="text-sm text-zinc-300 group-hover:text-zinc-200 transition-colors">Auto-clip</span>
            <button
              onClick={() => setAutoClip((v) => !v)}
              role="switch"
              aria-checked={autoClip}
              className={`focus-ring relative h-5 w-9 rounded-full transition-colors duration-200 ${
                autoClip ? "bg-accent" : "bg-border-active"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200 ${
                  autoClip ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
          </label>

          {/* Max clips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-zinc-300">Max clips</span>
              <span className="font-mono text-xs tabular-nums text-zinc-500">{maxClips}</span>
            </div>
            <input
              type="range"
              min={1}
              max={50}
              value={maxClips}
              onChange={(e) => setMaxClips(Number(e.target.value))}
              className="w-full accent-accent"
              aria-label="Maximum number of clips"
            />
          </div>

          {/* Min duration */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-zinc-300">Min duration</span>
              <span className="font-mono text-xs tabular-nums text-zinc-500">{minDuration}s</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              value={minDuration}
              onChange={(e) => setMinDuration(Number(e.target.value))}
              className="w-full accent-accent"
              aria-label="Minimum clip duration in seconds"
            />
          </div>

          {/* Max duration */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-zinc-300">Max duration</span>
              <span className="font-mono text-xs tabular-nums text-zinc-500">{maxDuration}s</span>
            </div>
            <input
              type="range"
              min={5}
              max={300}
              step={5}
              value={maxDuration}
              onChange={(e) => setMaxDuration(Number(e.target.value))}
              className="w-full accent-accent"
              aria-label="Maximum clip duration in seconds"
            />
          </div>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex items-start gap-2.5 rounded-xl bg-red-500/8 border border-red-500/15 p-3 animate-fade-in" role="alert">
          <AlertCircle className="h-4 w-4 mt-0.5 text-red-400 shrink-0" />
          <p className="text-sm text-red-300">{(error as Error).message}</p>
        </div>
      )}
    </div>
  );
}
