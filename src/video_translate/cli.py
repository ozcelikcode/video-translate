from __future__ import annotations

from pathlib import Path

import typer

from video_translate.config import load_config
from video_translate.pipeline.m1 import run_m1_pipeline
from video_translate.preflight import preflight_errors, run_preflight
from video_translate.utils.subprocess_utils import CommandExecutionError

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("doctor")
def doctor(
    config_path: Path | None = typer.Option(
        None, "--config", help="Optional TOML config file to override defaults."
    ),
) -> None:
    """Validate local environment dependencies for the pipeline."""
    config = load_config(config_path)
    report = run_preflight(yt_dlp_bin=config.tools.yt_dlp, ffmpeg_bin=config.tools.ffmpeg)
    errors = preflight_errors(report)

    typer.echo(f"Python: {report.python_version}")
    typer.echo(f"yt-dlp: {report.yt_dlp.path or 'MISSING'}")
    typer.echo(f"ffmpeg: {report.ffmpeg.path or 'MISSING'}")
    typer.echo(f"faster_whisper: {'OK' if report.faster_whisper_available else 'MISSING'}")

    if errors:
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=4)

    typer.echo("Doctor check passed.")


@app.command("run-m1")
def run_m1(
    url: str = typer.Option(..., "--url", help="YouTube video URL."),
    config_path: Path | None = typer.Option(
        None, "--config", help="Optional TOML config file to override defaults."
    ),
    workspace: Path | None = typer.Option(None, "--workspace", help="Run workspace directory."),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional explicit run id."),
    emit_srt: bool = typer.Option(True, "--emit-srt/--no-emit-srt", help="Write SRT output."),
) -> None:
    """Run M1 pipeline: ingest + normalize + ASR."""
    try:
        config = load_config(config_path)
        preflight_report = run_preflight(yt_dlp_bin=config.tools.yt_dlp, ffmpeg_bin=config.tools.ffmpeg)
        errors = preflight_errors(preflight_report)
        if errors:
            for error in errors:
                typer.echo(f"- {error}", err=True)
            raise typer.Exit(code=4)
        artifacts = run_m1_pipeline(
            source_url=url,
            config=config,
            workspace_dir=workspace,
            run_id=run_id,
            emit_srt=emit_srt,
            preflight_report=preflight_report,
        )
    except FileExistsError as exc:
        typer.echo(f"Run directory already exists: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except typer.Exit:
        raise
    except CommandExecutionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected pipeline failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Run root: {artifacts.run_root}")
    typer.echo(f"Source media: {artifacts.source_media}")
    typer.echo(f"Normalized audio: {artifacts.normalized_audio}")
    typer.echo(f"Transcript JSON: {artifacts.transcript_json}")
    if artifacts.transcript_srt:
        typer.echo(f"Transcript SRT: {artifacts.transcript_srt}")
    typer.echo(f"QA Report: {artifacts.qa_report}")
    typer.echo(f"Run Manifest: {artifacts.run_manifest}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
