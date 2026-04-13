"""AI analysis layer: Gemma 4 client, prompts, analysis pipeline, and ranking."""

from gemma_clipper.ai.analyzer import AnalysisSettings, ChunkAnalysis, VideoAnalysis, analyze_chunk, analyze_video
from gemma_clipper.ai.gemma_client import GemmaClient, extract_json
from gemma_clipper.ai.ranker import ClipSelection, RankedScene, rank_scenes, select_best_clips

__all__ = [
    "AnalysisSettings",
    "ChunkAnalysis",
    "ClipSelection",
    "GemmaClient",
    "RankedScene",
    "VideoAnalysis",
    "analyze_chunk",
    "analyze_video",
    "extract_json",
    "rank_scenes",
    "select_best_clips",
]
