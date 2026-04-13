"""
End-to-end integration tests using a real video file (Big Buck Bunny).
No mocks. Exercises the actual ffmpeg/whisper pipeline.

YouTube tests are conditional (require cookies on headless servers).
Gemma AI tests are conditional (require vLLM running).
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from gemma_clipper.config import Settings
from gemma_clipper.core.video import probe_video, extract_segment, extract_frame, get_keyframes
from gemma_clipper.core.scenes import detect_scenes
from gemma_clipper.core.silence import detect_silence, detect_speech_regions
from gemma_clipper.core.export import export_clip, ExportOptions
from gemma_clipper.ai.ranker import rank_scenes, select_best_clips
from gemma_clipper.ai.analyzer import ChunkAnalysis
from gemma_clipper.ai.gemma_client import GemmaClient
from gemma_clipper.db import init_db, get_db

# Sample video: Big Buck Bunny 320x180 (public domain, ~10 min)
SAMPLE_VIDEO = Path("test_output_e2e/sample_video.mp4")
YOUTUBE_URL = "https://www.youtube.com/watch?v=SHKB9XxOFlg"
TEST_DIR = Path("test_output_e2e")
SETTINGS = Settings(
    upload_dir=TEST_DIR / "uploads",
    output_dir=TEST_DIR / "output",
    thumbnails_dir=TEST_DIR / "thumbnails",
    db_path=TEST_DIR / "test_jobs.db",
)


@pytest.fixture(scope="session", autouse=True)
def setup_dirs():
    """Create test directories."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS.ensure_dirs()
    yield


def _require_video():
    if not SAMPLE_VIDEO.exists():
        pytest.skip("Sample video not found. Download Big Buck Bunny first.")
    return SAMPLE_VIDEO


# ── Video probing ───────────────────────────────────────────────────

class TestVideoProbe:
    def test_probe_video(self):
        path = _require_video()
        meta = asyncio.run(probe_video(path))
        assert meta.duration > 0
        assert meta.width > 0
        assert meta.height > 0
        assert meta.fps > 0
        print(f"\n  Duration: {meta.duration:.1f}s")
        print(f"  Resolution: {meta.width}x{meta.height}")
        print(f"  FPS: {meta.fps}")
        print(f"  Codec: {meta.codec}")
        print(f"  Size: {meta.filesize_mb:.1f} MB")

    def test_get_keyframes(self):
        path = _require_video()
        keyframes = asyncio.run(get_keyframes(path))
        assert len(keyframes) > 0, "Should find at least one keyframe"
        print(f"\n  Keyframes found: {len(keyframes)}")
        print(f"  First 5: {keyframes[:5]}")


# ── Scene detection ─────────────────────────────────────────────────

_detected_scenes = []


class TestSceneDetection:
    def test_detect_scenes(self):
        global _detected_scenes
        path = _require_video()
        scenes = asyncio.run(detect_scenes(path, threshold=0.3))
        _detected_scenes = scenes
        assert len(scenes) > 0, "Should detect at least one scene"
        for s in scenes:
            assert s.end_time > s.start_time
            assert s.duration > 0
        print(f"\n  Scenes detected: {len(scenes)}")
        for i, s in enumerate(scenes[:10]):
            print(f"    Scene {i+1}: {s.start_time:.1f}s - {s.end_time:.1f}s ({s.duration:.1f}s, score={s.score:.3f})")


# ── Silence detection ───────────────────────────────────────────────

class TestSilenceDetection:
    def test_detect_silence(self):
        path = _require_video()
        silence = asyncio.run(detect_silence(path, threshold_db=-30.0, min_duration=0.5))
        print(f"\n  Silent regions: {len(silence)}")
        for i, s in enumerate(silence[:5]):
            print(f"    Silence {i+1}: {s.start_time:.1f}s - {s.end_time:.1f}s ({s.duration:.1f}s)")

    def test_detect_speech_regions(self):
        path = _require_video()
        speech = asyncio.run(detect_speech_regions(path, threshold_db=-30.0, min_duration=0.5))
        # Big Buck Bunny has music, so speech regions represent non-silent audio
        print(f"\n  Speech/audio regions: {len(speech)}")
        for i, s in enumerate(speech[:5]):
            print(f"    Region {i+1}: {s.start_time:.1f}s - {s.end_time:.1f}s ({s.duration:.1f}s)")


# ── Frame/segment extraction ───────────────────────────────────────

class TestExtraction:
    def test_extract_frame(self):
        path = _require_video()
        out = SETTINGS.thumbnails_dir / "test_frame.jpg"
        result = asyncio.run(extract_frame(path, 5.0, out))
        assert result.exists(), "Frame should be extracted"
        assert result.stat().st_size > 1000, "Frame file too small"
        print(f"\n  Frame extracted: {result} ({result.stat().st_size / 1024:.1f} KB)")

    def test_extract_segment(self):
        path = _require_video()
        out = SETTINGS.output_dir / "test_segment.mp4"
        result = asyncio.run(extract_segment(path, 10.0, 20.0, out, max_width=320, crf=28))
        assert result.exists(), "Segment should be extracted"
        assert result.stat().st_size > 10_000, "Segment file too small"
        meta = asyncio.run(probe_video(result))
        assert 8.0 <= meta.duration <= 12.0, f"Segment duration should be ~10s, got {meta.duration}"
        print(f"\n  Segment: {result} ({result.stat().st_size / 1024:.1f} KB, {meta.duration:.1f}s)")


# ── Export ──────────────────────────────────────────────────────────

class TestExport:
    def test_export_clip_mp4(self):
        path = _require_video()
        out = SETTINGS.output_dir / "clip_mp4.mp4"
        opts = ExportOptions(format="mp4", crf=28, max_width=320)
        result = asyncio.run(export_clip(path, 30.0, 40.0, out, opts))
        assert result.exists()
        meta = asyncio.run(probe_video(result))
        assert meta.width <= 320
        print(f"\n  MP4 clip: {result} ({result.stat().st_size / 1024:.1f} KB, {meta.width}x{meta.height})")

    def test_export_clip_portrait(self):
        path = _require_video()
        out = SETTINGS.output_dir / "clip_portrait.mp4"
        opts = ExportOptions(format="mp4", crf=28, max_width=320, aspect_ratio="9:16")
        result = asyncio.run(export_clip(path, 30.0, 40.0, out, opts))
        assert result.exists()
        meta = asyncio.run(probe_video(result))
        assert meta.height > meta.width, f"Portrait should be taller: {meta.width}x{meta.height}"
        print(f"\n  Portrait clip: {result} ({meta.width}x{meta.height})")

    def test_export_clip_gif(self):
        path = _require_video()
        out = SETTINGS.output_dir / "clip_test.gif"
        opts = ExportOptions(format="gif", max_width=160)
        result = asyncio.run(export_clip(path, 50.0, 53.0, out, opts))
        assert result.exists()
        assert result.stat().st_size > 5_000
        print(f"\n  GIF clip: {result} ({result.stat().st_size / 1024:.1f} KB)")


# ── Ranker (pure logic, uses real scene data) ───────────────────────

class TestRanker:
    def test_rank_with_real_scenes(self):
        if not _detected_scenes:
            pytest.skip("No scenes detected")

        chunks = []
        for i, scene in enumerate(_detected_scenes):
            chunks.append(ChunkAnalysis(
                chunk_index=i,
                start_time=scene.start_time,
                end_time=scene.end_time,
                description=f"Scene {i+1}",
                objects=[],
                mood="neutral",
                energy_level=min(scene.score * 2, 1.0),
                audio_type="speech",
                interest_score=0.5 + (scene.score * 0.5),
                tags=[],
                suggested_clips=[],
            ))

        ranked = rank_scenes(chunks)
        assert len(ranked) == len(chunks)
        for i in range(len(ranked) - 1):
            assert ranked[i].final_score >= ranked[i + 1].final_score

        clips = select_best_clips(ranked, max_clips=3, min_duration=2.0, max_duration=30.0)
        assert len(clips) > 0
        assert len(clips) <= 3

        print(f"\n  Ranked {len(ranked)} scenes")
        print(f"  Selected {len(clips)} clips:")
        for c in clips:
            print(f"    {c.start_time:.1f}s - {c.end_time:.1f}s (score={c.score:.3f})")


# ── Database ────────────────────────────────────────────────────────

class TestDatabase:
    def test_init_and_crud(self):
        async def _test():
            import uuid
            import gemma_clipper.db as db_mod
            original = db_mod.settings.db_path
            db_mod.settings.db_path = SETTINGS.db_path
            job_id = f"test-job-{uuid.uuid4().hex[:8]}"
            try:
                await init_db()
                conn = await get_db()
                try:
                    await conn.execute(
                        "INSERT INTO jobs (id, source_type, source_name) VALUES (?, ?, ?)",
                        (job_id, "upload", "Big Buck Bunny"),
                    )
                    await conn.commit()
                    cursor = await conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
                    row = await cursor.fetchone()
                    assert row is not None
                    assert row["source_name"] == "Big Buck Bunny"
                    assert row["status"] == "pending"

                    await conn.execute(
                        "INSERT INTO scenes (id, job_id, start_time, end_time, duration) VALUES (?, ?, ?, ?, ?)",
                        (f"scene-{uuid.uuid4().hex[:8]}", job_id, 0.0, 10.0, 10.0),
                    )
                    await conn.commit()
                    cursor = await conn.execute("SELECT COUNT(*) as cnt FROM scenes WHERE job_id = ?", (job_id,))
                    row = await cursor.fetchone()
                    assert row["cnt"] == 1
                    print("\n  DB CRUD: insert job, insert scene, read back: all OK")
                finally:
                    await conn.close()
            finally:
                db_mod.settings.db_path = original

        asyncio.run(_test())


# ── YouTube (conditional, requires cookies) ─────────────────────────

class TestYouTube:
    def test_youtube_download(self):
        """Only runs if cookies are available (skips on headless servers)."""
        from gemma_clipper.core.youtube import download_video
        try:
            result = asyncio.run(
                download_video(YOUTUBE_URL, SETTINGS.upload_dir, max_resolution=480)
            )
            assert result.path.exists()
            print(f"\n  Downloaded: {result.title} ({result.duration:.1f}s)")
        except Exception as e:
            if "Sign in" in str(e) or "bot" in str(e):
                pytest.skip("YouTube requires cookies (headless server). Add cookies.txt to project root.")
            raise


# ── Gemma AI (conditional, requires vLLM) ───────────────────────────

class TestGemmaAI:
    def test_gemma_health(self):
        client = GemmaClient()
        healthy = asyncio.run(client.health_check())
        if not healthy:
            pytest.skip("vLLM not reachable, skipping AI tests")
        print("\n  vLLM is reachable!")

    def test_analyze_chunk(self):
        client = GemmaClient()
        if not asyncio.run(client.health_check()):
            pytest.skip("vLLM not reachable")

        path = _require_video()
        segment_path = SETTINGS.output_dir / "ai_test_segment.mp4"

        async def _test():
            seg = await extract_segment(path, 30.0, 40.0, segment_path, max_width=320, crf=30)
            video_bytes = seg.read_bytes()
            from gemma_clipper.ai.prompts import SCENE_ANALYSIS_PROMPT
            result = await client.analyze_video_chunk(video_bytes, SCENE_ANALYSIS_PROMPT)
            return result

        result = asyncio.run(_test())
        assert len(result) > 10, "Should get a non-trivial response from Gemma"
        print(f"\n  Gemma response length: {len(result)} chars")
        print(f"  First 200 chars: {result[:200]}")


# ── Full pipeline integration ───────────────────────────────────────

class TestFullPipeline:
    def test_download_detect_rank_export(self):
        """The golden path: probe -> detect scenes -> rank -> export clips."""
        path = _require_video()

        async def _pipeline():
            # 1. Probe
            meta = await probe_video(path)
            assert meta.duration > 0
            print(f"\n  1. Probed: {meta.duration:.1f}s, {meta.width}x{meta.height}")

            # 2. Scene detection
            scenes = await detect_scenes(path, threshold=0.3)
            print(f"  2. Scenes: {len(scenes)} detected")

            # 3. Silence detection
            silence = await detect_silence(path)
            speech = await detect_speech_regions(path)
            print(f"  3. Audio: {len(silence)} silent, {len(speech)} active regions")

            # 4. Generate thumbnails for first 3 scenes
            thumbs = []
            for i, scene in enumerate(scenes[:3]):
                mid = (scene.start_time + scene.end_time) / 2
                thumb_path = SETTINGS.thumbnails_dir / f"pipeline_scene_{i}.jpg"
                t = await extract_frame(path, mid, thumb_path)
                thumbs.append(t)
            print(f"  4. Thumbnails: {len(thumbs)} generated")

            # 5. Build rankings from scene data
            chunks = []
            for i, scene in enumerate(scenes):
                has_speech = any(
                    s.start_time < scene.end_time and s.end_time > scene.start_time
                    for s in speech
                )
                chunks.append(ChunkAnalysis(
                    chunk_index=i,
                    start_time=scene.start_time,
                    end_time=scene.end_time,
                    description=f"Scene {i+1}",
                    objects=[],
                    mood="neutral",
                    energy_level=min(scene.score * 2, 1.0),
                    audio_type="speech" if has_speech else "ambient",
                    interest_score=0.5 + (scene.score * 0.3),
                    tags=[],
                    suggested_clips=[],
                ))
            ranked = rank_scenes(chunks)
            print(f"  5. Ranked: top score={ranked[0].final_score:.3f}")

            # 6. Select clips
            clips = select_best_clips(ranked, max_clips=3, min_duration=3.0, max_duration=30.0)
            print(f"  6. Selected: {len(clips)} clips")

            # 7. Export each clip
            exported = []
            for i, clip in enumerate(clips):
                out = SETTINGS.output_dir / f"final_clip_{i}.mp4"
                opts = ExportOptions(format="mp4", crf=26, max_width=320)
                result = await export_clip(path, clip.start_time, clip.end_time, out, opts)
                exported.append(result)
                clip_meta = await probe_video(result)
                print(f"  7.{i+1} Exported: {result.name} ({clip_meta.duration:.1f}s, {result.stat().st_size/1024:.0f}KB)")

            assert len(exported) == len(clips)
            for e in exported:
                assert e.exists()
                assert e.stat().st_size > 5_000

            # 8. Save results JSON
            results = {
                "video": str(path),
                "duration": meta.duration,
                "scenes_count": len(scenes),
                "clips": [
                    {
                        "file": str(exported[i]),
                        "start": clips[i].start_time,
                        "end": clips[i].end_time,
                        "score": clips[i].score,
                        "reason": clips[i].reason,
                    }
                    for i in range(len(clips))
                ],
            }
            results_path = SETTINGS.output_dir / "results.json"
            results_path.write_text(json.dumps(results, indent=2))
            print(f"  8. Results saved to {results_path}")

            return exported

        exported = asyncio.run(_pipeline())
        assert len(exported) > 0, "Should have exported at least one clip"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
