import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchJobs,
  fetchJob,
  uploadVideo,
  createYouTubeJob,
  exportClips,
  deleteJob,
  fetchHealth,
  type JobResponse,
  type JobDetail,
  type ExportOptions,
  type HealthResponse,
} from "../api/client";

const ACTIVE_STATUSES = new Set([
  "pending",
  "downloading",
  "processing",
  "analyzing",
]);

function jobIsActive(job: JobResponse | JobDetail): boolean {
  return ACTIVE_STATUSES.has(job.status);
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
    retry: false,
  });
}

// ---------------------------------------------------------------------------
// Job list
// ---------------------------------------------------------------------------

export function useJobs() {
  return useQuery<JobResponse[]>({
    queryKey: ["jobs"],
    queryFn: () => fetchJobs(),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.some(jobIsActive)) return 3_000;
      return 10_000;
    },
  });
}

// ---------------------------------------------------------------------------
// Single job detail (polls while active)
// ---------------------------------------------------------------------------

export function useJob(jobId: string | null) {
  return useQuery<JobDetail>({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && jobIsActive(data)) return 3_000;
      return false;
    },
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateUploadJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      options,
      onProgress,
    }: {
      file: File;
      options: {
        auto_clip: boolean;
        max_clips: number;
        min_clip_duration: number;
        max_clip_duration: number;
      };
      onProgress?: (pct: number) => void;
    }) => uploadVideo(file, options, onProgress),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useCreateYouTubeJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      url,
      options,
    }: {
      url: string;
      options: {
        auto_clip: boolean;
        max_clips: number;
        min_clip_duration: number;
        max_clip_duration: number;
      };
    }) => createYouTubeJob(url, options),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useExportClips() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      jobId,
      options,
    }: {
      jobId: string;
      options: ExportOptions;
    }) => exportClips(jobId, options),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["job", vars.jobId] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useDeleteJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}
