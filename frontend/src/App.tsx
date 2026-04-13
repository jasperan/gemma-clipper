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
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ---------------------------------------------------------------- */}
      {/* Header                                                           */}
      {/* ---------------------------------------------------------------- */}
      <header className="flex items-center justify-between border-b border-slate-800 bg-slate-900/80 px-5 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <Scissors className="h-5 w-5 text-emerald-400" />
          <h1 className="text-lg font-bold tracking-tight text-slate-100">
            gemma-clipper
          </h1>
          {health.data?.version && (
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
              v{health.data.version}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Backend status */}
          <div className="flex items-center gap-1.5">
            {backendUp ? (
              <Wifi className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <WifiOff className="h-3.5 w-3.5 text-red-400" />
            )}
            <span
              className={`text-xs ${backendUp ? "text-slate-400" : "text-red-400"}`}
            >
              {backendUp ? "Connected" : "Offline"}
            </span>
          </div>

          {/* vLLM status */}
          {backendUp && (
            <div className="flex items-center gap-1.5">
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${
                  connected ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              <span className="text-xs text-slate-500">
                {connected ? "vLLM" : "vLLM offline"}
              </span>
            </div>
          )}
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Body: sidebar + main                                             */}
      {/* ---------------------------------------------------------------- */}
      <div className="flex flex-1 overflow-hidden">
        {/* ---- Sidebar ------------------------------------------------- */}
        <aside className="flex w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-900/50">
          {/* Upload panel */}
          <div className="border-b border-slate-800 p-4">
            <VideoUpload onJobCreated={onJobCreated} />
          </div>

          {/* Job list */}
          <div className="flex-1 overflow-y-auto p-2">
            <JobList
              selectedJobId={selectedJobId}
              onSelect={(id) => {
                setSelectedJobId(id);
                setSelectedSceneIds(new Set());
              }}
            />
          </div>
        </aside>

        {/* ---- Main content area --------------------------------------- */}
        <main className="flex flex-1 flex-col overflow-hidden">
          {!selectedJobId ? (
            /* Empty state */
            <div className="flex flex-1 items-center justify-center">
              <div className="text-center">
                <Film className="mx-auto mb-4 h-16 w-16 text-slate-700" />
                <h2 className="text-lg font-medium text-slate-400">
                  Upload a video or paste a YouTube URL
                </h2>
                <p className="mt-1 text-sm text-slate-600">
                  AI will detect the best moments and generate clips
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Job header bar */}
              <div className="flex items-center justify-between border-b border-slate-800 px-6 py-3">
                <div className="flex items-center gap-2 min-w-0">
                  <ChevronRight className="h-4 w-4 text-slate-600 shrink-0" />
                  <h2 className="truncate text-sm font-semibold text-slate-200">
                    {jobData?.source_name || selectedJobId.slice(0, 12)}
                  </h2>
                  {jobData?.video_duration != null && (
                    <span className="shrink-0 rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-500">
                      {formatDuration(jobData.video_duration)}
                    </span>
                  )}
                </div>

                {/* Tabs */}
                {jobData?.status === "complete" && (
                  <div className="flex gap-1">
                    <button
                      onClick={() => setActiveTab("scenes")}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        activeTab === "scenes"
                          ? "bg-slate-700 text-slate-200"
                          : "text-slate-500 hover:text-slate-300"
                      }`}
                    >
                      <LayoutGrid className="h-3.5 w-3.5" />
                      Scenes ({scenes.length})
                    </button>
                    <button
                      onClick={() => setActiveTab("clips")}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        activeTab === "clips"
                          ? "bg-slate-700 text-slate-200"
                          : "text-slate-500 hover:text-slate-300"
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
                    <JobProgress
                      status={jobData.status}
                      progress={jobData.progress}
                      error={jobData.error}
                    />
                  )}

                  {/* Failed state */}
                  {jobData?.status === "failed" && (
                    <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
                      <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-red-400" />
                      <p className="text-sm font-medium text-red-300">
                        Processing failed
                      </p>
                      {jobData.error && (
                        <p className="mt-1 text-sm text-red-400/80">
                          {jobData.error}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Complete: scenes or clips */}
                  {jobData?.status === "complete" && (
                    <>
                      {activeTab === "scenes" ? (
                        <SceneList
                          scenes={scenes}
                          selectedIds={selectedSceneIds}
                          onToggle={toggleScene}
                        />
                      ) : (
                        <ClipPreview clips={clips} />
                      )}
                    </>
                  )}
                </div>

                {/* Export sidebar (visible when complete) */}
                {jobData?.status === "complete" && clips.length > 0 && (
                  <div className="w-72 shrink-0 overflow-y-auto border-l border-slate-800 p-4">
                    <ExportPanel
                      jobId={jobData.id}
                      clips={clips}
                      selectedSceneIds={selectedSceneIds}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
