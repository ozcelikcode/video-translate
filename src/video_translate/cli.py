from __future__ import annotations

from pathlib import Path

import typer

from video_translate.config import load_config
from video_translate.pipeline.m1 import run_m1_pipeline
from video_translate.pipeline.m2_benchmark import run_m2_profile_benchmark
from video_translate.pipeline.m2 import run_m2_pipeline
from video_translate.pipeline.m2_prep import prepare_m2_translation_input
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
    report = run_preflight(
        yt_dlp_bin=config.tools.yt_dlp,
        ffmpeg_bin=config.tools.ffmpeg,
        translate_backend=config.translate.backend,
        check_translate_backend=True,
    )
    errors = preflight_errors(report)

    typer.echo(f"Python: {report.python_version}")
    typer.echo(f"yt-dlp: {report.yt_dlp.path or 'MISSING'}")
    typer.echo(f"ffmpeg: {report.ffmpeg.path or 'MISSING'}")
    typer.echo(f"faster_whisper: {'OK' if report.faster_whisper_available else 'MISSING'}")
    if report.translate_backend == "transformers":
        typer.echo(f"transformers: {'OK' if report.transformers_available else 'MISSING'}")
        typer.echo(f"sentencepiece: {'OK' if report.sentencepiece_available else 'MISSING'}")
        typer.echo(f"torch: {'OK' if report.torch_available else 'MISSING'}")

    if errors:
        for error in errors:
            typer.echo(f"- {error}", err=True)
        raise typer.Exit(code=4)

    typer.echo("Doctor check passed.")


@app.command("prepare-m2")
def prepare_m2(
    run_root: Path | None = typer.Option(
        None, "--run-root", help="Run root directory created by run-m1."
    ),
    transcript_json: Path | None = typer.Option(
        None,
        "--transcript-json",
        help="Explicit path to transcript JSON. If set, --run-root is optional.",
    ),
    output_json: Path | None = typer.Option(
        None,
        "--output-json",
        help="Optional explicit output JSON path for translation input contract.",
    ),
    target_lang: str = typer.Option("tr", "--target-lang", help="Target translation language code."),
) -> None:
    """Prepare M2 translation input contract from M1 transcript."""
    source_transcript = transcript_json
    if source_transcript is None:
        if run_root is None:
            raise typer.BadParameter("Either --run-root or --transcript-json must be provided.")
        source_transcript = run_root / "output" / "transcript" / "transcript.en.json"

    resolved_output = output_json
    if resolved_output is None:
        if run_root is not None:
            resolved_output = (
                run_root / "output" / "translate" / f"translation_input.en-{target_lang}.json"
            )
        else:
            resolved_output = (
                source_transcript.parent.parent
                / "translate"
                / f"translation_input.en-{target_lang}.json"
            )

    try:
        output_path = prepare_m2_translation_input(
            transcript_json_path=source_transcript,
            output_json_path=resolved_output,
            target_language=target_lang,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=5) from exc
    except ValueError as exc:
        typer.echo(f"Invalid input for M2 prep: {exc}", err=True)
        raise typer.Exit(code=6) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M2 prep failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M2 translation input: {output_path}")


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
        preflight_report = run_preflight(
            yt_dlp_bin=config.tools.yt_dlp,
            ffmpeg_bin=config.tools.ffmpeg,
            translate_backend=config.translate.backend,
            check_translate_backend=False,
        )
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


@app.command("run-m2")
def run_m2(
    run_root: Path | None = typer.Option(
        None, "--run-root", help="Run root directory created by run-m1."
    ),
    translation_input: Path | None = typer.Option(
        None,
        "--translation-input",
        help="Path to translation input contract. If omitted, derived from --run-root.",
    ),
    output_json: Path | None = typer.Option(
        None, "--output-json", help="Optional explicit output JSON path."
    ),
    qa_report_json: Path | None = typer.Option(
        None, "--qa-report-json", help="Optional explicit M2 QA report JSON path."
    ),
    target_lang: str | None = typer.Option(
        None,
        "--target-lang",
        help="Optional override for target language code.",
    ),
    config_path: Path | None = typer.Option(
        None, "--config", help="Optional TOML config file to override defaults."
    ),
) -> None:
    """Run M2 pipeline: translation output + QA report."""
    config = load_config(config_path)
    preflight_report = run_preflight(
        yt_dlp_bin=config.tools.yt_dlp,
        ffmpeg_bin=config.tools.ffmpeg,
        translate_backend=config.translate.backend,
        check_translate_backend=True,
    )
    preflight_issue_list = preflight_errors(preflight_report)
    if preflight_issue_list:
        for issue in preflight_issue_list:
            typer.echo(f"- {issue}", err=True)
        raise typer.Exit(code=4)

    resolved_target_lang = target_lang or config.translate.target_language

    resolved_input = translation_input
    if resolved_input is None:
        if run_root is None:
            raise typer.BadParameter("Either --run-root or --translation-input must be provided.")
        resolved_input = (
            run_root / "output" / "translate" / f"translation_input.en-{resolved_target_lang}.json"
        )

    resolved_output = output_json
    if resolved_output is None:
        if run_root is not None:
            resolved_output = (
                run_root / "output" / "translate" / f"translation_output.en-{resolved_target_lang}.json"
            )
        else:
            resolved_output = (
                resolved_input.parent / f"translation_output.en-{resolved_target_lang}.json"
            )

    resolved_qa_report = qa_report_json
    if resolved_qa_report is None:
        if run_root is not None:
            resolved_qa_report = run_root / "output" / "qa" / "m2_qa_report.json"
        else:
            resolved_qa_report = resolved_input.parent.parent / "qa" / "m2_qa_report.json"

    if run_root is not None:
        resolved_manifest = run_root / "run_m2_manifest.json"
    else:
        resolved_manifest = resolved_input.parent.parent.parent / "run_m2_manifest.json"

    try:
        artifacts = run_m2_pipeline(
            translation_input_json_path=resolved_input,
            output_json_path=resolved_output,
            qa_report_json_path=resolved_qa_report,
            run_manifest_json_path=resolved_manifest,
            config=config,
            target_language_override=resolved_target_lang,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=7) from exc
    except ValueError as exc:
        typer.echo(f"Invalid input for M2 run: {exc}", err=True)
        raise typer.Exit(code=8) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=9) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M2 pipeline failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M2 input: {artifacts.translation_input_json}")
    typer.echo(f"M2 output: {artifacts.translation_output_json}")
    typer.echo(f"M2 QA report: {artifacts.qa_report_json}")
    typer.echo(f"M2 run manifest: {artifacts.run_manifest_json}")


@app.command("benchmark-m2")
def benchmark_m2(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    translation_input: Path | None = typer.Option(
        None,
        "--translation-input",
        help="Optional explicit translation input path. Defaults to run-root path.",
    ),
    config_path: list[Path] = typer.Option(
        [],
        "--config",
        help="Config path(s). Use multiple --config entries to compare profiles.",
    ),
) -> None:
    """Benchmark multiple M2 profiles on the same translation input."""
    resolved_input = translation_input or (run_root / "output" / "translate" / "translation_input.en-tr.json")
    configs = config_path or [
        Path("configs/profiles/gtx1650_i5_12500h.toml"),
        Path("configs/profiles/gtx1650_fast.toml"),
    ]
    try:
        report_path = run_m2_profile_benchmark(
            run_root=run_root,
            translation_input_json=resolved_input,
            config_paths=configs,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=10) from exc
    except ValueError as exc:
        typer.echo(f"Invalid benchmark input: {exc}", err=True)
        raise typer.Exit(code=11) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected benchmark failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M2 benchmark report: {report_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
