import { useState, useMemo } from "react";
import {
  Scissors,
  Wifi,
  WifiOff,
  Film,
  ChevronRight,
  LayoutGrid,
  List,
  AlertTriangle,
} from "lucide-react";
import { useHealth, useJob } from "./hooks/useJobs";
import VideoUpload from "./components/VideoUpload";
import JobList from "./components/JobList";
import JobProgress from "./components/JobProgress";
import SceneList from "./components/SceneList";
import ClipPreview from "./components/ClipPreview";
import ExportPanel from "./components/ExportPanel";

type Tab = "scenes" | "clips";

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "--:--";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Keep formatBytes available for future use (file size display)
void formatBytes;

export default function App() {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedSceneIds, setSelectedSceneIds] = useState<Set<string>>(
    new Set(),
  );
  const [activeTab, setActiveTab] = useState<Tab>("scenes");

  const health = useHealth();
  const job = useJob(selectedJobId);

  const jobData = job.data;
  const isActive =
    jobData &&
    ["pending", "downloading", "processing", "analyzing"].includes(
      jobData.status,
    );

  const scenes = useMemo(() => jobData?.scenes ?? [], [jobData]);
  const clips = useMemo(() => jobData?.clips ?? [], [jobData]);

  const toggleScene = (id: string) => {
    setSelectedSceneIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const onJobCreated = (id: string) => {
    setSelectedJobId(id);
    setSelectedSceneIds(new Set());
    setActiveTab("scenes");
  };

  const connected = health.data?.vllm_connected ?? false;
  const backendUp = !!health.data;

  return (
    <div className="flex min-h-[100dvh] flex-col overflow-hidden bg-surface">
      {/* Skip to content link */}
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between border-b border-border bg-surface-raised/80 px-5 py-3.5 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-muted">
            <Scissors className="h-4 w-4 text-accent" />
          </div>
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-base font-semibold tracking-tight text-zinc-100">
              Gemma Clipper
            </h1>
            {health.data?.version && (
              <span className="rounded-md bg-surface-overlay px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-zinc-500">
                v{health.data.version}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Backend status */}
          <div className="flex items-center gap-2">
            {backendUp ? (
              <Wifi className="h-3.5 w-3.5 text-accent" />
            ) : (
              <WifiOff className="h-3.5 w-3.5 text-red-400" />
            )}
            <span
              className={`text-xs font-medium ${backendUp ? "text-zinc-400" : "text-red-400"}`}
            >
              {backendUp ? "Connected" : "Offline"}
            </span>
          </div>

          {/* vLLM status */}
          {backendUp && (
            <div className="flex items-center gap-2">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  connected
                    ? "bg-accent shadow-[0_0_6px_rgba(52,211,153,0.4)]"
                    : "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.3)]"
                }`}
              />
              <span className="text-xs text-zinc-500">
                {connected ? "vLLM" : "vLLM offline"}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Body: sidebar + main */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="flex w-[280px] shrink-0 flex-col border-r border-border bg-surface-raised">
          {/* Upload panel */}
          <div className="border-b border-border p-4">
            <VideoUpload onJobCreated={onJobCreated} />
          </div>

          {/* Job list */}
          <nav className="flex-1 overflow-y-auto p-2" aria-label="Job history">
            <JobList
              selectedJobId={selectedJobId}
              onSelect={(id) => {
                setSelectedJobId(id);
                setSelectedSceneIds(new Set());
              }}
            />
          </nav>
        </aside>

        {/* Main content area */}
        <main id="main-content" className="flex flex-1 flex-col overflow-hidden bg-surface">
          {!selectedJobId ? (
            /* Empty state */
            <div className="flex flex-1 items-center justify-center">
              <div className="relative text-center">
                {/* Ambient glow behind icon */}
                <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-32 w-32 rounded-full bg-accent-glow blur-2xl" />
                <Film className="relative mx-auto mb-5 h-14 w-14 text-zinc-700" />
                <h2 className="relative text-lg font-semibold text-zinc-300 text-balance">
                  Upload a video or paste a YouTube URL
                </h2>
                <p className="relative mt-2 text-sm text-zinc-500 text-pretty">
                  AI detects the best moments and generates clips automatically
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Job header bar */}
              <div className="flex items-center justify-between border-b border-border bg-surface-raised/50 px-6 py-3.5">
                <div className="flex items-center gap-2.5 min-w-0">
                  <ChevronRight className="h-4 w-4 text-zinc-600 shrink-0" />
                  <h2 className="truncate text-sm font-semibold text-zinc-200">
                    {jobData?.source_name || selectedJobId.slice(0, 12)}
                  </h2>
                  {jobData?.video_duration != null && (
                    <span className="shrink-0 rounded-md bg-surface-overlay px-2 py-0.5 font-mono text-[10px] tabular-nums text-zinc-500">
                      {formatDuration(jobData.video_duration)}
                    </span>
                  )}
                </div>

                {/* Tabs */}
                {jobData?.status === "complete" && (
                  <div className="flex gap-1 rounded-lg bg-surface-overlay p-0.5">
                    <button
                      onClick={() => setActiveTab("scenes")}
                      className={`focus-ring flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                        activeTab === "scenes"
                          ? "bg-surface-raised text-zinc-200 shadow-card"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                      Scenes ({scenes.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("clips")}
                      className={`focus-ring flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                        activeTab === "clips"
                          ? "bg-surface-raised text-zinc-200 shadow-card"
                          : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <List className="h-3.5 w-3.5" />
                      Clips ({clips.length})
                    </button>
                  </div>
                )}
              </div>

              {/* Content area */}
              <div className="flex flex-1 overflow-hidden">
                <div className="flex-1 overflow-y-auto p-6">
                  {/* Progress for active jobs */}
                  {isActive && jobData && (
                    <div className="animate-fade-in">
                      <JobProgress
                        status={jobData.status}
                        progress={jobData.progress}
                        error={jobData.error}
                      />
                    </div>
                  )}

                  {/* Failed state */}
                  {jobData?.status === "failed" && (
                    <div className="animate-fade-in rounded-2xl border border-red-500/15 bg-red-500/5 p-6 text-center">
                      <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-red-400" />
                      <p className="text-sm font-semibold text-red-300">
                        Processing failed
                      </p>
                      {jobData.error && (
                        <p className="mt-1.5 text-sm text-red-400/70">
                          {jobData.error}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Complete: scenes or clips */}
                  {jobData?.status === "complete" && (
                    <div className="animate-fade-in">
                      {activeTab === "scenes" ? (
                        <SceneList
                          scenes={scenes}
                          selectedIds={selectedSceneIds}
                          onToggle={toggleScene}
                        />
                      ) : (
                        <ClipPreview clips={clips} />
                      )}
                    </div>
                  )}
                </div>

                {/* Export sidebar (visible when complete) */}
                {jobData?.status === "complete" && clips.length > 0 && (
                  <aside className="w-[280px] shrink-0 overflow-y-auto border-l border-border bg-surface-raised/50 p-4 animate-fade-in">
                    <ExportPanel
                      jobId={jobData.id}
                      clips={clips}
                      selectedSceneIds={selectedSceneIds}
                    />
                  </aside>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
