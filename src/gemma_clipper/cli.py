"""Typer CLI for gemma-clipper."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from gemma_clipper import __version__
from gemma_clipper.config import settings

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="gemma-clipper",
    help="AI-powered video clipping with Gemma 4",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_youtube_url(source: str) -> bool:
    """Return True if *source* looks like a YouTube URL."""
    return source.startswith("http") and ("youtube" in source or "youtu.be" in source)


def _format_time(seconds: float) -> str:
    """Format seconds as MM:SS.ms or HH:MM:SS.ms."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h:
        return f"{h:d}:{m:02d}:{s:05.2f}"
    return f"{m:d}:{s:05.2f}"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"gemma-clipper [bold]{__version__}[/bold]")
        raise typer.Exit()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


@app.command()
def analyze(
    source: str = typer.Argument(..., help="Path to MP4 file or YouTube URL"),
    max_clips: int = typer.Option(10, "--max-clips", "-n", help="Maximum clips to select"),
    min_duration: float = typer.Option(5.0, "--min-duration", help="Minimum clip duration (s)"),
    max_duration: float = typer.Option(60.0, "--max-duration", help="Maximum clip duration (s)"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory"),
    no_auto_clip: bool = typer.Option(False, "--no-auto-clip", help="Skip automatic clip selection"),
    threshold: float = typer.Option(0.3, "--threshold", "-t", help="Scene-change threshold"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    version: Optional[bool] = typer.Option(None, "--version", callback=_version_callback, is_eager=True, help="Show version"),
) -> None:
    """Run the full analysis pipeline on a video.

    SOURCE can be a local MP4 file path or a YouTube URL.
    """
    _setup_logging(verbose)
    asyncio.run(_analyze_impl(
        source=source,
        max_clips=max_clips,
        min_duration=min_duration,
        max_duration=max_duration,
        output_dir=Path(output_dir),
        no_auto_clip=no_auto_clip,
        threshold=threshold,
    ))


async def _analyze_impl(
    source: str,
    max_clips: int,
    min_duration: float,
    max_duration: float,
    output_dir: Path,
    no_auto_clip: bool,
    threshold: float,
) -> None:
    from gemma_clipper.ai.analyzer import AnalysisSettings, analyze_video
    from gemma_clipper.ai.gemma_client import GemmaClient
    from gemma_clipper.ai.ranker import rank_scenes, select_best_clips
    from gemma_clipper.core.scenes import SceneBoundary, detect_scenes
    from gemma_clipper.core.video import probe_video
    from gemma_clipper.core.youtube import download_video

    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        # -- Stage 1: acquire video ----------------------------------------
        is_yt = _is_youtube_url(source)
        video_path: Path

        if is_yt:
            task_dl = progress.add_task("Downloading video...", total=1)
            result = await download_video(source, output_dir)
            video_path = result.path
            progress.update(task_dl, completed=1, description=f"Downloaded: {result.title}")
        else:
            video_path = Path(source)
            if not video_path.exists():
                err_console.print(Panel(f"[red]File not found:[/red] {source}", title="Error"))
                raise typer.Exit(code=1)

        # -- Stage 2: probe ------------------------------------------------
        task_probe = progress.add_task("Probing video...", total=1)
        meta = await probe_video(video_path)
        progress.update(task_probe, completed=1, description=f"Probed: {meta.duration:.1f}s, {meta.width}x{meta.height}")

        # -- Stage 3: scene detection --------------------------------------
        task_scenes = progress.add_task("Detecting scenes...", total=1)
        scene_boundaries: list[SceneBoundary] = await detect_scenes(video_path, threshold)
        progress.update(task_scenes, completed=1, description=f"Scenes: {len(scene_boundaries)} found")

        if not scene_boundaries:
            console.print(Panel("[yellow]No scene changes detected. Try lowering --threshold.[/yellow]", title="Warning"))
            raise typer.Exit(code=0)

        # -- Stage 4: AI analysis ------------------------------------------
        task_ai = progress.add_task("AI analysis (Gemma 4)...", total=len(scene_boundaries))

        scenes_as_dicts = [
            {
                "id": str(i),
                "start_time": sb.start_time,
                "end_time": sb.end_time,
            }
            for i, sb in enumerate(scene_boundaries)
        ]

        async with GemmaClient() as client:
            analysis = await analyze_video(
                client,
                video_path,
                scenes_as_dicts,
                settings=AnalysisSettings(),
                total_duration=meta.duration,
            )
        progress.update(task_ai, completed=len(scene_boundaries), description="AI analysis complete")

        # -- Stage 5: ranking ----------------------------------------------
        task_rank = progress.add_task("Ranking scenes...", total=1)
        ranked = rank_scenes(analysis.chunks)
        progress.update(task_rank, completed=1, description=f"Ranked {len(ranked)} scenes")

        # -- Stage 6: clip selection (optional) ----------------------------
        clips = []
        if not no_auto_clip:
            task_clip = progress.add_task("Selecting clips...", total=1)
            clips = select_best_clips(ranked, max_clips=max_clips, min_duration=min_duration, max_duration=max_duration)
            progress.update(task_clip, completed=1, description=f"Selected {len(clips)} clips")

    # -- Display ranked scenes table -----------------------------------
    console.print()
    scene_table = Table(title="Ranked Scenes", show_lines=True)
    scene_table.add_column("#", style="dim", width=4, justify="right")
    scene_table.add_column("Start", justify="right")
    scene_table.add_column("End", justify="right")
    scene_table.add_column("Duration", justify="right")
    scene_table.add_column("Score", justify="right")
    scene_table.add_column("Description", max_width=50)

    for rs in ranked[:20]:
        dur = rs.end_time - rs.start_time
        score_color = "green" if rs.final_score >= 0.6 else "yellow" if rs.final_score >= 0.3 else "red"
        scene_table.add_row(
            str(rs.rank),
            _format_time(rs.start_time),
            _format_time(rs.end_time),
            f"{dur:.1f}s",
            f"[{score_color}]{rs.final_score:.3f}[/{score_color}]",
            (rs.description[:50] + "...") if len(rs.description) > 50 else rs.description,
        )
    console.print(scene_table)

    # -- Display selected clips table ----------------------------------
    if clips:
        console.print()
        clip_table = Table(title="Selected Clips", show_lines=True)
        clip_table.add_column("#", style="dim", width=4, justify="right")
        clip_table.add_column("Start", justify="right")
        clip_table.add_column("End", justify="right")
        clip_table.add_column("Duration", justify="right")
        clip_table.add_column("Score", justify="right")
        clip_table.add_column("Reason", max_width=60)

        for idx, clip in enumerate(clips, start=1):
            dur = clip.end_time - clip.start_time
            clip_table.add_row(
                str(idx),
                _format_time(clip.start_time),
                _format_time(clip.end_time),
                f"{dur:.1f}s",
                f"{clip.score:.3f}",
                clip.reason,
            )
        console.print(clip_table)

    # -- Save results JSON ---------------------------------------------
    results = {
        "version": __version__,
        "source": source,
        "video_path": str(video_path),
        "duration": meta.duration,
        "scenes": [
            {
                "rank": rs.rank,
                "scene_id": rs.scene_id,
                "start_time": rs.start_time,
                "end_time": rs.end_time,
                "score": rs.final_score,
                "breakdown": rs.breakdown,
                "description": rs.description,
            }
            for rs in ranked
        ],
        "clips": [
            {
                "index": idx,
                "start_time": c.start_time,
                "end_time": c.end_time,
                "duration": c.end_time - c.start_time,
                "score": c.score,
                "reason": c.reason,
                "source_scenes": c.source_scenes,
            }
            for idx, c in enumerate(clips, start=1)
        ],
    }

    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    console.print()
    console.print(Panel(
        f"[green]Analysis complete.[/green]\n"
        f"Scenes: {len(ranked)} ranked | Clips: {len(clips)} selected\n"
        f"Results saved to: {results_path}",
        title="Done",
    ))


# ---------------------------------------------------------------------------
# scenes
# ---------------------------------------------------------------------------


@app.command()
def scenes(
    source: str = typer.Argument(..., help="Path to MP4 file or YouTube URL"),
    threshold: float = typer.Option(0.3, "--threshold", "-t", help="Scene-change threshold (0.0-1.0)"),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Detect scenes in a video (no AI analysis)."""
    _setup_logging(verbose)
    asyncio.run(_scenes_impl(source, threshold, output_json))


async def _scenes_impl(source: str, threshold: float, output_json: bool) -> None:
    from gemma_clipper.core.scenes import detect_scenes
    from gemma_clipper.core.youtube import download_video

    video_path: Path
    if _is_youtube_url(source):
        with console.status("Downloading video..."):
            result = await download_video(source, Path("output"))
            video_path = result.path
    else:
        video_path = Path(source)
        if not video_path.exists():
            err_console.print(Panel(f"[red]File not found:[/red] {source}", title="Error"))
            raise typer.Exit(code=1)

    with console.status("Detecting scenes..."):
        scene_boundaries = await detect_scenes(video_path, threshold)

    if output_json:
        data = [
            {
                "index": i,
                "start_time": sb.start_time,
                "end_time": sb.end_time,
                "duration": sb.duration,
                "score": sb.score,
            }
            for i, sb in enumerate(scene_boundaries, start=1)
        ]
        console.print_json(json.dumps(data, indent=2))
        return

    table = Table(title=f"Scenes ({len(scene_boundaries)} detected)", show_lines=True)
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Change Score", justify="right")

    for i, sb in enumerate(scene_boundaries, start=1):
        score_color = "green" if sb.score >= 0.6 else "yellow" if sb.score >= 0.3 else "dim"
        table.add_row(
            str(i),
            _format_time(sb.start_time),
            _format_time(sb.end_time),
            f"{sb.duration:.1f}s",
            f"[{score_color}]{sb.score:.3f}[/{score_color}]",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# clips
# ---------------------------------------------------------------------------


@app.command()
def clips(
    job_or_path: str = typer.Argument(..., help="Path to results JSON or a job ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Display clips from a results JSON file or job ID."""
    _setup_logging(verbose)

    path = Path(job_or_path)
    if path.exists() and path.suffix == ".json":
        _display_clips_from_json(path)
    else:
        asyncio.run(_display_clips_from_db(job_or_path))


def _display_clips_from_json(path: Path) -> None:
    """Load and display clips from a results JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        err_console.print(Panel(f"[red]Failed to read JSON:[/red] {exc}", title="Error"))
        raise typer.Exit(code=1)

    clip_list = data.get("clips", [])
    if not clip_list:
        console.print(Panel("[yellow]No clips found in results file.[/yellow]", title="Info"))
        raise typer.Exit(code=0)

    table = Table(title=f"Clips ({len(clip_list)} total)", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Reason", max_width=60)

    for clip in clip_list:
        table.add_row(
            str(clip.get("index", "")),
            _format_time(clip["start_time"]),
            _format_time(clip["end_time"]),
            f"{clip.get('duration', clip['end_time'] - clip['start_time']):.1f}s",
            f"{clip.get('score', 0):.3f}",
            clip.get("reason", ""),
        )
    console.print(table)


async def _display_clips_from_db(job_id: str) -> None:
    """Query the database for clips by job ID."""
    from gemma_clipper.db import get_db

    try:
        db = await get_db()
    except Exception as exc:
        err_console.print(Panel(f"[red]Database error:[/red] {exc}", title="Error"))
        raise typer.Exit(code=1)

    try:
        cursor = await db.execute(
            "SELECT * FROM clips WHERE job_id = ? ORDER BY interest_score DESC",
            (job_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        err_console.print(Panel(f"[yellow]No clips found for job:[/yellow] {job_id}", title="Info"))
        raise typer.Exit(code=0)

    table = Table(title=f"Clips for job {job_id}", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Reason", max_width=60)

    for idx, row in enumerate(rows, start=1):
        dur = row["end_time"] - row["start_time"]
        table.add_row(
            str(idx),
            _format_time(row["start_time"]),
            _format_time(row["end_time"]),
            f"{dur:.1f}s",
            f"{row['interest_score']:.3f}",
            row["reason"] or "",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@app.command(name="export")
def export_cmd(
    source: str = typer.Argument(..., help="Path to results JSON or video file"),
    fmt: str = typer.Option("mp4", "--format", "-f", help="Export format (mp4/webm/gif)"),
    aspect_ratio: str = typer.Option("original", "--aspect-ratio", "-a", help="Aspect ratio (original/16:9/9:16/1:1)"),
    captions: bool = typer.Option(False, "--captions", help="Add captions to exported clips"),
    caption_style: str = typer.Option("default", "--caption-style", help="Caption style (default/bold/minimal)"),
    crf: int = typer.Option(23, "--crf", help="CRF quality (0=lossless, 51=worst)"),
    max_width: Optional[int] = typer.Option(None, "--max-width", help="Maximum width in pixels"),
    output_dir: str = typer.Option("output/clips", "--output-dir", "-o", help="Output directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Export clips from a previous analysis."""
    _setup_logging(verbose)
    asyncio.run(_export_impl(
        source=source,
        fmt=fmt,
        aspect_ratio=aspect_ratio,
        captions=captions,
        caption_style=caption_style,
        crf=crf,
        max_width=max_width,
        output_dir=Path(output_dir),
    ))


async def _export_impl(
    source: str,
    fmt: str,
    aspect_ratio: str,
    captions: bool,
    caption_style: str,
    crf: int,
    max_width: int | None,
    output_dir: Path,
) -> None:
    from gemma_clipper.core.captions import burn_captions, generate_srt, transcribe
    from gemma_clipper.core.export import ClipSpec, ExportOptions, export_batch

    source_path = Path(source)
    if not source_path.exists():
        err_console.print(Panel(f"[red]File not found:[/red] {source}", title="Error"))
        raise typer.Exit(code=1)

    # Determine if source is a results JSON or a raw video
    if source_path.suffix == ".json":
        data = json.loads(source_path.read_text(encoding="utf-8"))
        video_path = Path(data["video_path"])
        clip_list = data.get("clips", [])
        if not clip_list:
            err_console.print(Panel("[yellow]No clips found in results file.[/yellow]", title="Info"))
            raise typer.Exit(code=0)
        if not video_path.exists():
            err_console.print(Panel(f"[red]Source video not found:[/red] {video_path}", title="Error"))
            raise typer.Exit(code=1)
    else:
        err_console.print(Panel(
            "[yellow]Provide a results JSON from a previous analysis.\n"
            "Run 'gemma-clipper analyze' first.[/yellow]",
            title="Info",
        ))
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    opts = ExportOptions(
        format=fmt,
        crf=crf,
        max_width=max_width or settings.max_resolution_width,
        aspect_ratio=aspect_ratio,
    )
    clip_specs = [
        ClipSpec(
            start_time=c["start_time"],
            end_time=c["end_time"],
            label=f"clip_{c.get('index', i):04d}",
        )
        for i, c in enumerate(clip_list, start=1)
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_export = progress.add_task("Exporting clips...", total=len(clip_specs))

        exported_paths = await export_batch(video_path, clip_specs, output_dir, opts)
        progress.update(task_export, completed=len(clip_specs))

        # Burn captions if requested
        if captions:
            task_cap = progress.add_task("Adding captions...", total=len(exported_paths))
            for idx, clip_path in enumerate(exported_paths):
                transcript = await transcribe(clip_path)
                srt_path = clip_path.with_suffix(".srt")
                await generate_srt(transcript, srt_path)
                captioned_out = clip_path.with_stem(clip_path.stem + "_captioned")
                await burn_captions(clip_path, srt_path, captioned_out, style=caption_style)
                progress.update(task_cap, advance=1)

    console.print()
    table = Table(title="Exported Clips", show_lines=True)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("File")
    table.add_column("Format")

    for idx, p in enumerate(exported_paths, start=1):
        table.add_row(str(idx), str(p), fmt)
    console.print(table)

    console.print(Panel(
        f"[green]Exported {len(exported_paths)} clips to {output_dir}[/green]",
        title="Done",
    ))


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------


@app.command()
def download(
    url: str = typer.Argument(..., help="YouTube URL to download"),
    max_resolution: int = typer.Option(1080, "--max-resolution", "-r", help="Maximum resolution"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Download a YouTube video."""
    _setup_logging(verbose)
    asyncio.run(_download_impl(url, max_resolution, Path(output_dir)))


async def _download_impl(url: str, max_resolution: int, output_dir: Path) -> None:
    from gemma_clipper.core.youtube import download_video

    if not _is_youtube_url(url):
        err_console.print(Panel(f"[red]Not a valid YouTube URL:[/red] {url}", title="Error"))
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Downloading...", total=1)
        result = await download_video(url, output_dir, max_resolution=max_resolution)
        progress.update(task, completed=1, description="Download complete")

    console.print()
    console.print(Panel(
        f"[green]Downloaded:[/green] {result.title}\n"
        f"Duration: {_format_time(result.duration)}\n"
        f"Path: {result.path}",
        title="Done",
    ))


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8080, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Start the FastAPI API server."""
    _setup_logging(verbose)
    import uvicorn

    console.print(Panel(
        f"Starting server on [bold]{host}:{port}[/bold]\n"
        f"Reload: {'on' if reload else 'off'}",
        title="gemma-clipper API",
    ))
    uvicorn.run(
        "gemma_clipper.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if verbose else "info",
    )


# ---------------------------------------------------------------------------
# captions
# ---------------------------------------------------------------------------


@app.command()
def captions(
    source: str = typer.Argument(..., help="Path to video file"),
    model: str = typer.Option("base", "--model", "-m", help="Whisper model size (tiny/base/small/medium/large)"),
    fmt: str = typer.Option("srt", "--format", "-f", help="Caption format (srt/vtt)"),
    burn: bool = typer.Option(False, "--burn", "-b", help="Burn captions into the video"),
    style: str = typer.Option("default", "--style", "-s", help="Caption style (default/bold/minimal)"),
    output_dir: str = typer.Option("output", "--output-dir", "-o", help="Output directory"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Transcribe and generate captions for a video."""
    _setup_logging(verbose)
    asyncio.run(_captions_impl(
        source=source,
        model=model,
        fmt=fmt,
        burn=burn,
        style=style,
        output_dir=Path(output_dir),
    ))


async def _captions_impl(
    source: str,
    model: str,
    fmt: str,
    burn: bool,
    style: str,
    output_dir: Path,
) -> None:
    from gemma_clipper.core.captions import (
        burn_captions,
        generate_srt,
        generate_vtt,
        transcribe,
    )

    video_path = Path(source)
    if not video_path.exists():
        err_console.print(Panel(f"[red]File not found:[/red] {source}", title="Error"))
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_tr = progress.add_task("Transcribing...", total=1)
        transcript = await transcribe(video_path, model_name=model)
        progress.update(task_tr, completed=1, description=f"Transcribed: {len(transcript.segments)} segments ({transcript.language})")

        # Generate caption file
        stem = video_path.stem
        if fmt == "vtt":
            caption_path = output_dir / f"{stem}.vtt"
            await generate_vtt(transcript, caption_path)
        else:
            caption_path = output_dir / f"{stem}.srt"
            await generate_srt(transcript, caption_path)

        console.print(f"Caption file: {caption_path}")

        # Burn captions if requested
        if burn:
            task_burn = progress.add_task("Burning captions...", total=1)
            srt_path = caption_path
            if fmt == "vtt":
                srt_path = output_dir / f"{stem}.srt"
                await generate_srt(transcript, srt_path)
            burned_output = output_dir / f"{stem}_captioned.mp4"
            await burn_captions(video_path, srt_path, burned_output, style=style)
            progress.update(task_burn, completed=1, description="Captions burned")
            console.print(f"Captioned video: {burned_output}")

    # Show transcript preview
    console.print()
    table = Table(title="Transcript Preview (first 10 segments)", show_lines=True)
    table.add_column("Start", justify="right")
    table.add_column("End", justify="right")
    table.add_column("Text", max_width=70)

    for seg in transcript.segments[:10]:
        table.add_row(
            _format_time(seg.start),
            _format_time(seg.end),
            seg.text,
        )
    if len(transcript.segments) > 10:
        table.add_row("...", "...", f"({len(transcript.segments) - 10} more segments)")
    console.print(table)

    console.print(Panel(
        f"[green]Transcription complete.[/green]\n"
        f"Language: {transcript.language}\n"
        f"Segments: {len(transcript.segments)}\n"
        f"Caption file: {caption_path}",
        title="Done",
    ))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
