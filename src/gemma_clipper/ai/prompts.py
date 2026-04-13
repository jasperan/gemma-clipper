"""Prompt templates for Gemma 4 video analysis."""

from __future__ import annotations

SCENE_ANALYSIS_PROMPT = """\
Analyze this video segment carefully. Describe what you observe across these dimensions:

1. What is happening in the scene (actions, events, transitions)
2. People and objects visible
3. Mood and energy level
4. Any text visible on screen
5. Audio characteristics (speech, music, ambient sounds, or silence)

Return your analysis as a single JSON object with exactly these fields:
- "description": string, 2-3 sentence summary of the scene
- "objects": list of strings, notable people/objects visible
- "mood": string, one-word mood descriptor (e.g. "energetic", "calm", "tense", "humorous")
- "energy_level": float 0.0 to 1.0, how visually/audibly active the segment is
- "text_visible": string, any on-screen text (empty string if none)
- "audio_type": one of "speech", "music", "ambient", "silent"

Return ONLY the JSON object, no other text.\
"""

HIGHLIGHT_DETECTION_PROMPT = """\
You are evaluating a video segment for its potential as a social media clip.

Context about the full video:
- Total duration: {total_duration:.1f} seconds
- This is chunk {chunk_index} of {total_chunks}
- Time range: {start_time:.1f}s to {end_time:.1f}s

Rate how interesting and engaging this segment would be as a standalone short-form clip. \
Consider: visual appeal, emotional impact, humor, surprise, action, clear speech, and shareability.

Return a single JSON object with exactly these fields:
- "interest_score": float 0.0 to 1.0, overall engagement potential
- "reasons": list of strings, 2-4 short reasons for the score
- "suggested_clip_boundaries": list of objects, each with "start_offset" (float, seconds from chunk start), "end_offset" (float, seconds from chunk start), and "reason" (string). Empty list if no strong clip candidates.
- "tags": list of strings, content tags for this segment (e.g. "funny", "tutorial", "reaction", "music")

Return ONLY the JSON object, no other text.\
"""

SCENE_RANKING_PROMPT = """\
Given the following scene analyses from a video, re-rank them by engagement potential \
for social media clips. Consider visual variety, speech content, emotional peaks, \
and action density when ranking.

Scene analyses:
{scenes_json}

Return a single JSON object with exactly this field:
- "ranked_scenes": list of objects, each with:
  - "scene_id": string, the original scene ID
  - "final_score": float 0.0 to 1.0
  - "rank_reason": string, one sentence explaining the ranking

Order the list from highest to lowest final_score.

Return ONLY the JSON object, no other text.\
"""

CONTENT_SUMMARY_PROMPT = """\
Given the following scene-by-scene analyses of a video, produce an overall summary.

Scene analyses:
{scenes_json}

Total video duration: {total_duration:.1f} seconds

Return a single JSON object with exactly these fields:
- "title": string, a concise descriptive title for the video (under 80 chars)
- "summary": string, 2-4 sentence summary of the full video content
- "key_topics": list of strings, main topics or themes covered
- "best_moments": list of objects, each with "timestamp" (float, seconds) and "description" (string), \
highlighting the most notable moments

Return ONLY the JSON object, no other text.\
"""


def format_prompt(template: str, **kwargs: object) -> str:
    """Format a prompt template with the given keyword arguments."""
    return template.format(**kwargs)
