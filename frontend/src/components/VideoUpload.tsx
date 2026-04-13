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
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !busy && fileRef.current?.click()}
        className={`
          relative cursor-pointer rounded-xl border-2 border-dashed
          transition-all duration-200 p-8 text-center
          ${
            dragOver
              ? "border-emerald-400 bg-emerald-500/10"
              : "border-slate-600 hover:border-slate-500 bg-slate-800/50"
          }
          ${busy ? "pointer-events-none opacity-60" : ""}
        `}
      >
        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={onFileChange}
        />
        <Upload className="mx-auto mb-3 h-8 w-8 text-slate-400" />
        <p className="text-sm font-medium text-slate-300">
          Drop a video file here or click to browse
        </p>
        <p className="mt-1 text-xs text-slate-500">
          MP4, MOV, AVI, MKV, WebM
        </p>

        {uploadPct !== null && (
          <div className="mt-4">
            <div className="h-1.5 w-full rounded-full bg-slate-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${uploadPct}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-slate-400">{uploadPct}% uploaded</p>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-700" />
        <span className="text-xs text-slate-500 uppercase tracking-wider">
          or
        </span>
        <div className="h-px flex-1 bg-slate-700" />
      </div>

      {/* YouTube input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Youtube className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Paste YouTube URL..."
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitYouTube()}
            onPaste={() =>
              setTimeout(() => {
                // auto-submit on paste if looks like a URL
                const v = (
                  document.querySelector(
                    'input[placeholder="Paste YouTube URL..."]',
                  ) as HTMLInputElement
                )?.value;
                if (v && (v.includes("youtube.com") || v.includes("youtu.be"))) {
                  // give React state a tick
                }
              }, 100)
            }
            className="w-full rounded-lg border border-slate-600 bg-slate-800 py-2.5 pl-10 pr-3
                       text-sm text-slate-200 placeholder-slate-500
                       focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          />
        </div>
        <button
          onClick={submitYouTube}
          disabled={busy || !youtubeUrl.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white
                     hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors"
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
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-300 transition-colors"
      >
        <Settings2 className="h-3.5 w-3.5" />
        {showOptions ? "Hide options" : "Clipping options"}
      </button>

      {showOptions && (
        <div className="space-y-3 rounded-lg border border-slate-700 bg-slate-800/60 p-4 animate-in fade-in">
          {/* Auto-clip toggle */}
          <label className="flex items-center justify-between">
            <span className="text-sm text-slate-300">Auto-clip</span>
            <button
              onClick={() => setAutoClip((v) => !v)}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                autoClip ? "bg-emerald-500" : "bg-slate-600"
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                  autoClip ? "left-[18px]" : "left-0.5"
                }`}
              />
            </button>
          </label>

          {/* Max clips */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-slate-300">Max clips</span>
              <span className="font-mono text-xs text-slate-400">{maxClips}</span>
            </div>
            <input
              type="range"
              min={1}
              max={50}
              value={maxClips}
              onChange={(e) => setMaxClips(Number(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>

          {/* Min duration */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-slate-300">Min duration</span>
              <span className="font-mono text-xs text-slate-400">{minDuration}s</span>
            </div>
            <input
              type="range"
              min={1}
              max={30}
              value={minDuration}
              onChange={(e) => setMinDuration(Number(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>

          {/* Max duration */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-slate-300">Max duration</span>
              <span className="font-mono text-xs text-slate-400">{maxDuration}s</span>
            </div>
            <input
              type="range"
              min={5}
              max={300}
              step={5}
              value={maxDuration}
              onChange={(e) => setMaxDuration(Number(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>
        </div>
      )}

      {/* Error display */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg bg-red-500/10 border border-red-500/20 p-3">
          <AlertCircle className="h-4 w-4 mt-0.5 text-red-400 shrink-0" />
          <p className="text-sm text-red-300">{(error as Error).message}</p>
        </div>
      )}
    </div>
  );
}
