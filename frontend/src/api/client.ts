// ---------------------------------------------------------------------------
// Types matching the backend models
// ---------------------------------------------------------------------------

export type JobStatus =
  | "pending"
  | "downloading"
  | "processing"
  | "analyzing"
  | "complete"
  | "failed";

export interface JobResponse {
  id: string;
  status: JobStatus;
  source_type: string;
  source_name: string;
  video_duration: number | null;
  scenes_found: number;
  clips_generated: number;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface Scene {
  id: string;
  start_time: number;
  end_time: number;
  duration: number;
  thumbnail_path: string | null;
  description: string;
  interest_score: number;
  tags: string[];
  has_speech: boolean;
  has_music: boolean;
  is_silent: boolean;
}

export interface Clip {
  id: string;
  job_id: string;
  start_time: number;
  end_time: number;
  duration: number;
  source_scene_ids: string[];
  reason: string;
  interest_score: number;
  exported_path: string | null;
  thumbnail_path: string | null;
}

export interface JobDetail extends JobResponse {
  scenes: Scene[];
  clips: Clip[];
}

export interface HealthResponse {
  status: string;
  version: string;
  vllm_connected: boolean;
  ffmpeg_available: boolean;
}

export interface ExportOptions {
  clip_ids: string[];
  format: string;
  aspect_ratio: string;
  add_captions: boolean;
  caption_style: string;
  crf: number;
  max_width: number;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/");
}

export function fetchJobs(status?: string): Promise<JobResponse[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<JobResponse[]>(`/api/videos${qs}`);
}

export function fetchJob(jobId: string): Promise<JobDetail> {
  return request<JobDetail>(`/api/videos/${jobId}`);
}

export function deleteJob(jobId: string): Promise<void> {
  return request<void>(`/api/videos/${jobId}`, { method: "DELETE" });
}

export function fetchClips(jobId: string): Promise<Clip[]> {
  return request<Clip[]>(`/api/clips/${jobId}`);
}

export function fetchScenes(jobId: string): Promise<Scene[]> {
  return request<Scene[]>(`/api/clips/${jobId}/scenes`);
}

export function exportClips(
  jobId: string,
  options: ExportOptions,
): Promise<Clip[]> {
  return request<Clip[]>(`/api/clips/${jobId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
}

export function createCustomClip(
  jobId: string,
  startTime: number,
  endTime: number,
): Promise<Clip> {
  return request<Clip>(`/api/clips/${jobId}/custom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_time: startTime, end_time: endTime }),
  });
}

export function createYouTubeJob(
  url: string,
  options: {
    auto_clip: boolean;
    max_clips: number;
    min_clip_duration: number;
    max_clip_duration: number;
  },
): Promise<JobResponse> {
  return request<JobResponse>("/api/videos/youtube", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, ...options }),
  });
}

/**
 * Upload a video file with progress tracking.
 * Returns a promise that resolves to the job response.
 * onProgress receives a 0-100 value.
 */
export function uploadVideo(
  file: File,
  options: {
    auto_clip: boolean;
    max_clips: number;
    min_clip_duration: number;
    max_clip_duration: number;
  },
  onProgress?: (pct: number) => void,
): Promise<JobResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/videos/upload");

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid JSON response"));
        }
      } else {
        reject(new Error(`${xhr.status}: ${xhr.responseText || xhr.statusText}`));
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Network error")));
    xhr.addEventListener("abort", () => reject(new Error("Upload aborted")));

    const fd = new FormData();
    fd.append("file", file);
    fd.append("auto_clip", String(options.auto_clip));
    fd.append("max_clips", String(options.max_clips));
    fd.append("min_clip_duration", String(options.min_clip_duration));
    fd.append("max_clip_duration", String(options.max_clip_duration));

    xhr.send(fd);
  });
}

export function clipDownloadUrl(clipId: string): string {
  return `/api/clips/download/${clipId}`;
}
