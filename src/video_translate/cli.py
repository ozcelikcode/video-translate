from __future__ import annotations

from pathlib import Path

import typer

from video_translate.config import load_config
from video_translate.pipeline.m1 import run_m1_pipeline
from video_translate.pipeline.full_run import run_full_dub_pipeline
from video_translate.pipeline.m2_benchmark import run_m2_profile_benchmark
from video_translate.pipeline.m2 import run_m2_pipeline
from video_translate.pipeline.m2_prep import prepare_m2_translation_input
from video_translate.pipeline.m3 import run_m3_pipeline
from video_translate.pipeline.m3_benchmark import run_m3_profile_benchmark
from video_translate.pipeline.m3_finalize import finalize_m3_profile_selection
from video_translate.pipeline.m3_closure import run_m3_closure_workflow
from video_translate.pipeline.m3_espeak_tune import run_m3_espeak_tuning_automation
from video_translate.pipeline.m3_prep import prepare_m3_tts_input
from video_translate.pipeline.m3_tuning_report import build_m3_tuning_report_markdown
from video_translate.preflight import preflight_errors, run_preflight
from video_translate.ui import run_ui_server
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
        tts_backend=config.tts.backend,
        espeak_bin=config.tts.espeak_bin,
        piper_bin=getattr(config.tts, "piper_bin", "piper"),
        piper_model_path=getattr(config.tts, "piper_model_path", None),
        check_translate_backend=True,
        check_tts_backend=True,
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
    if report.tts_backend == "espeak":
        typer.echo(f"espeak: {report.espeak.path if report.espeak and report.espeak.path else 'MISSING'}")
    if report.tts_backend == "piper":
        typer.echo(f"piper: {report.piper.path if report.piper and report.piper.path else 'MISSING'}")
        typer.echo(
            "piper_model: "
            + (
                report.piper_model_path
                if report.piper_model_exists
                else f"MISSING ({report.piper_model_path or 'tts.piper_model_path'})"
            )
        )

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


@app.command("prepare-m3")
def prepare_m3(
    run_root: Path | None = typer.Option(
        None, "--run-root", help="Run root directory created by run-m1."
    ),
    translation_output_json: Path | None = typer.Option(
        None,
        "--translation-output-json",
        help="Explicit path to M2 translation output JSON. If set, --run-root is optional.",
    ),
    output_json: Path | None = typer.Option(
        None,
        "--output-json",
        help="Optional explicit output JSON path for M3 TTS input contract.",
    ),
    target_lang: str | None = typer.Option(
        None,
        "--target-lang",
        help="Optional override for target language code.",
    ),
) -> None:
    """Prepare M3 TTS input contract from M2 translation output."""
    source_output = translation_output_json
    if source_output is None:
        if run_root is None:
            raise typer.BadParameter(
                "Either --run-root or --translation-output-json must be provided."
            )
        selected_lang = target_lang or "tr"
        source_output = (
            run_root / "output" / "translate" / f"translation_output.en-{selected_lang}.json"
        )

    resolved_output = output_json
    if resolved_output is None:
        if run_root is not None:
            selected_lang = target_lang or "tr"
            resolved_output = run_root / "output" / "tts" / f"tts_input.{selected_lang}.json"
        else:
            lang_suffix = target_lang or "tr"
            resolved_output = source_output.parent.parent / "tts" / f"tts_input.{lang_suffix}.json"

    try:
        output_path = prepare_m3_tts_input(
            translation_output_json_path=source_output,
            output_json_path=resolved_output,
            target_language=target_lang,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=12) from exc
    except ValueError as exc:
        typer.echo(f"Invalid input for M3 prep: {exc}", err=True)
        raise typer.Exit(code=13) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 prep failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 TTS input: {output_path}")


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
            tts_backend=config.tts.backend,
            espeak_bin=config.tts.espeak_bin,
            piper_bin=getattr(config.tts, "piper_bin", "piper"),
            piper_model_path=getattr(config.tts, "piper_model_path", None),
            check_translate_backend=False,
            check_tts_backend=False,
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


@app.command("run-dub")
def run_dub(
    url: str = typer.Option(..., "--url", help="YouTube video URL."),
    config_path: Path | None = typer.Option(
        None, "--config", help="Optional TOML config file to override defaults."
    ),
    workspace: Path | None = typer.Option(None, "--workspace", help="Run workspace directory."),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional explicit run id."),
    emit_srt: bool = typer.Option(True, "--emit-srt/--no-emit-srt", help="Write transcript SRT output."),
    target_lang: str | None = typer.Option(
        None,
        "--target-lang",
        help="Optional target language override. Defaults to config translate.target_language.",
    ),
    use_m3_closure: bool = typer.Option(
        False,
        "--m3-closure/--no-m3-closure",
        help="Use M3 closure workflow (optional auto-tune + strict QA gate final run).",
    ),
    base_config: Path = typer.Option(
        Path("configs/profiles/gtx1650_espeak.toml"),
        "--base-config",
        help="Base espeak config path used by M3 closure auto tuning.",
    ),
    tuned_output_config: Path = typer.Option(
        Path("configs/profiles/m3_espeak_recommended.toml"),
        "--tuned-output-config",
        help="Output path for tuned/locked profile in M3 closure flow.",
    ),
    auto_tune: bool = typer.Option(
        True,
        "--auto-tune/--no-auto-tune",
        help="Enable auto tuning when M3 closure flow is selected.",
    ),
    max_candidates: int = typer.Option(
        16,
        "--max-candidates",
        help="Maximum espeak candidate profile count for auto tuning.",
    ),
) -> None:
    """Run complete URL -> M1 -> M2 -> M3 dubbing flow with one command."""
    try:
        config = load_config(config_path)
        artifacts = run_full_dub_pipeline(
            source_url=url,
            config=config,
            workspace_dir=workspace,
            run_id=run_id,
            emit_srt=emit_srt,
            target_lang=target_lang,
            use_m3_closure=use_m3_closure,
            base_config_path=base_config,
            tuned_output_config_path=tuned_output_config,
            auto_tune=auto_tune,
            max_candidates=max_candidates,
        )
    except FileExistsError as exc:
        typer.echo(f"Run directory already exists: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except CommandExecutionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=28) from exc
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=29) from exc
    except ValueError as exc:
        typer.echo(f"Invalid run-dub input: {exc}", err=True)
        raise typer.Exit(code=30) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected run-dub failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Run root: {artifacts.run_root}")
    typer.echo(f"M1 transcript JSON: {artifacts.m1_artifacts.transcript_json}")
    typer.echo(f"M2 output: {artifacts.m2_artifacts.translation_output_json}")
    typer.echo(f"M3 output: {artifacts.m3_artifacts.tts_output_json}")
    typer.echo(f"M3 QA report: {artifacts.m3_artifacts.qa_report_json}")
    typer.echo(f"M3 stitched preview: {artifacts.m3_artifacts.stitched_preview_wav}")
    if artifacts.m3_closure_report_json:
        typer.echo(f"M3 closure report: {artifacts.m3_closure_report_json}")


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
        tts_backend=config.tts.backend,
        espeak_bin=config.tts.espeak_bin,
        piper_bin=getattr(config.tts, "piper_bin", "piper"),
        piper_model_path=getattr(config.tts, "piper_model_path", None),
        check_translate_backend=True,
        check_tts_backend=False,
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


@app.command("run-m3")
def run_m3(
    run_root: Path | None = typer.Option(
        None, "--run-root", help="Run root directory created by run-m1."
    ),
    tts_input: Path | None = typer.Option(
        None,
        "--tts-input",
        help="Path to M3 TTS input contract. If omitted, derived from --run-root.",
    ),
    output_json: Path | None = typer.Option(
        None, "--output-json", help="Optional explicit M3 output JSON path."
    ),
    qa_report_json: Path | None = typer.Option(
        None, "--qa-report-json", help="Optional explicit M3 QA report JSON path."
    ),
    target_lang: str = typer.Option("tr", "--target-lang", help="Target language code."),
    config_path: Path | None = typer.Option(
        None, "--config", help="Optional TOML config file to override defaults."
    ),
) -> None:
    """Run M3 pipeline: local TTS segment synthesis + QA report."""
    config = load_config(config_path)
    preflight_report = run_preflight(
        yt_dlp_bin=config.tools.yt_dlp,
        ffmpeg_bin=config.tools.ffmpeg,
        translate_backend=config.translate.backend,
        tts_backend=config.tts.backend,
        espeak_bin=config.tts.espeak_bin,
        piper_bin=getattr(config.tts, "piper_bin", "piper"),
        piper_model_path=getattr(config.tts, "piper_model_path", None),
        check_translate_backend=False,
        check_tts_backend=True,
    )
    preflight_issue_list = preflight_errors(preflight_report)
    if preflight_issue_list:
        for issue in preflight_issue_list:
            typer.echo(f"- {issue}", err=True)
        raise typer.Exit(code=4)

    resolved_input = tts_input
    if resolved_input is None:
        if run_root is None:
            raise typer.BadParameter("Either --run-root or --tts-input must be provided.")
        resolved_input = run_root / "output" / "tts" / f"tts_input.{target_lang}.json"

    resolved_output = output_json
    if resolved_output is None:
        if run_root is not None:
            resolved_output = run_root / "output" / "tts" / f"tts_output.{target_lang}.json"
        else:
            resolved_output = resolved_input.parent / f"tts_output.{target_lang}.json"

    resolved_qa_report = qa_report_json
    if resolved_qa_report is None:
        if run_root is not None:
            resolved_qa_report = run_root / "output" / "qa" / "m3_qa_report.json"
        else:
            resolved_qa_report = resolved_input.parent.parent / "qa" / "m3_qa_report.json"

    if run_root is not None:
        resolved_manifest = run_root / "run_m3_manifest.json"
    else:
        resolved_manifest = resolved_input.parent.parent.parent / "run_m3_manifest.json"

    try:
        artifacts = run_m3_pipeline(
            tts_input_json_path=resolved_input,
            output_json_path=resolved_output,
            qa_report_json_path=resolved_qa_report,
            run_manifest_json_path=resolved_manifest,
            config=config,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=14) from exc
    except ValueError as exc:
        typer.echo(f"Invalid input for M3 run: {exc}", err=True)
        raise typer.Exit(code=15) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=16) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 pipeline failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 input: {artifacts.tts_input_json}")
    typer.echo(f"M3 output: {artifacts.tts_output_json}")
    typer.echo(f"M3 QA report: {artifacts.qa_report_json}")
    typer.echo(f"M3 stitched preview: {artifacts.stitched_preview_wav}")
    typer.echo(f"M3 run manifest: {artifacts.run_manifest_json}")


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


@app.command("benchmark-m3")
def benchmark_m3(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    tts_input: Path | None = typer.Option(
        None,
        "--tts-input",
        help="Optional explicit TTS input path. Defaults to run-root path.",
    ),
    config_path: list[Path] = typer.Option(
        [],
        "--config",
        help="Config path(s). Use multiple --config entries to compare profiles.",
    ),
) -> None:
    """Benchmark multiple M3 profiles on the same TTS input."""
    resolved_input = tts_input or (run_root / "output" / "tts" / "tts_input.tr.json")
    configs = config_path or [
        Path("configs/profiles/gtx1650_i5_12500h.toml"),
        Path("configs/profiles/gtx1650_espeak.toml"),
    ]
    try:
        report_path = run_m3_profile_benchmark(
            run_root=run_root,
            tts_input_json=resolved_input,
            config_paths=configs,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=17) from exc
    except ValueError as exc:
        typer.echo(f"Invalid benchmark input: {exc}", err=True)
        raise typer.Exit(code=18) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected benchmark failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 benchmark report: {report_path}")


@app.command("report-m3-tuning")
def report_m3_tuning(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    benchmark_report_json: Path | None = typer.Option(
        None,
        "--benchmark-report-json",
        help="Optional explicit benchmark report JSON path.",
    ),
    output_markdown: Path | None = typer.Option(
        None,
        "--output-markdown",
        help="Optional explicit markdown report path.",
    ),
) -> None:
    """Generate M3 tuning markdown report from benchmark JSON."""
    try:
        report_path = build_m3_tuning_report_markdown(
            run_root=run_root,
            benchmark_report_json=benchmark_report_json,
            output_markdown_path=output_markdown,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=19) from exc
    except ValueError as exc:
        typer.echo(f"Invalid M3 tuning report input: {exc}", err=True)
        raise typer.Exit(code=20) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 tuning report failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 tuning report: {report_path}")


@app.command("finalize-m3-profile")
def finalize_m3_profile(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    benchmark_report_json: Path | None = typer.Option(
        None,
        "--benchmark-report-json",
        help="Optional explicit benchmark report JSON path.",
    ),
    output_config: Path | None = typer.Option(
        None,
        "--output-config",
        help="Optional output profile path. Defaults to configs/profiles/m3_recommended.toml.",
    ),
) -> None:
    """Finalize M3 profile selection and lock the recommended config."""
    try:
        artifacts = finalize_m3_profile_selection(
            run_root=run_root,
            benchmark_report_json=benchmark_report_json,
            output_config_path=output_config,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=21) from exc
    except ValueError as exc:
        typer.echo(f"Invalid M3 finalization input: {exc}", err=True)
        raise typer.Exit(code=22) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 finalization failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 recommended profile: {artifacts.recommended_profile}")
    typer.echo(f"M3 source config: {artifacts.source_config_path}")
    typer.echo(f"M3 locked config: {artifacts.output_config_path}")
    typer.echo(f"M3 selection report: {artifacts.selection_report_json}")


@app.command("tune-m3-espeak")
def tune_m3_espeak(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    tts_input: Path | None = typer.Option(
        None,
        "--tts-input",
        help="Optional explicit TTS input JSON path. Defaults to run-root path.",
    ),
    base_config: Path = typer.Option(
        Path("configs/profiles/gtx1650_espeak.toml"),
        "--base-config",
        help="Base espeak config path used to generate tuning candidates.",
    ),
    output_config: Path = typer.Option(
        Path("configs/profiles/m3_espeak_recommended.toml"),
        "--output-config",
        help="Output path for locked recommended profile.",
    ),
    max_candidates: int = typer.Option(
        16,
        "--max-candidates",
        help="Maximum candidate profile count for auto tuning.",
    ),
) -> None:
    """Run automated espeak tuning: generate candidates, benchmark, report, and lock profile."""
    resolved_tts_input = tts_input or (run_root / "output" / "tts" / "tts_input.tr.json")
    try:
        artifacts = run_m3_espeak_tuning_automation(
            run_root=run_root,
            tts_input_json=resolved_tts_input,
            base_config_path=base_config,
            output_config_path=output_config,
            max_candidates=max_candidates,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=23) from exc
    except ValueError as exc:
        typer.echo(f"Invalid M3 espeak tuning input: {exc}", err=True)
        raise typer.Exit(code=24) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 espeak tuning failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 espeak tuning candidates: {len(artifacts.generated_config_paths)}")
    typer.echo(f"M3 espeak benchmark: {artifacts.benchmark_report_json}")
    typer.echo(f"M3 espeak tuning report: {artifacts.tuning_report_markdown}")
    typer.echo(f"M3 recommended profile: {artifacts.recommended_profile}")
    typer.echo(f"M3 locked espeak config: {artifacts.recommended_config_path}")
    typer.echo(f"M3 selection report: {artifacts.selection_report_json}")


@app.command("finish-m3")
def finish_m3(
    run_root: Path = typer.Option(..., "--run-root", help="Run root directory created by run-m1."),
    target_lang: str = typer.Option("tr", "--target-lang", help="Target language code."),
    translation_output_json: Path | None = typer.Option(
        None,
        "--translation-output-json",
        help="Optional explicit translation output JSON path.",
    ),
    tts_input: Path | None = typer.Option(
        None,
        "--tts-input",
        help="Optional explicit TTS input JSON path.",
    ),
    base_config: Path = typer.Option(
        Path("configs/profiles/gtx1650_espeak.toml"),
        "--base-config",
        help="Base espeak config path for auto tuning.",
    ),
    tuned_output_config: Path = typer.Option(
        Path("configs/profiles/m3_espeak_recommended.toml"),
        "--tuned-output-config",
        help="Output path for tuned/locked profile.",
    ),
    auto_tune: bool = typer.Option(
        True,
        "--auto-tune/--no-auto-tune",
        help="Run espeak auto tuning before final M3 run.",
    ),
    max_candidates: int = typer.Option(
        16,
        "--max-candidates",
        help="Maximum espeak candidate count for auto tuning.",
    ),
) -> None:
    """Finish M3 workflow: prepare, optional espeak auto tuning, strict-gate final run."""
    try:
        artifacts = run_m3_closure_workflow(
            run_root=run_root,
            target_lang=target_lang,
            translation_output_json=translation_output_json,
            tts_input_json=tts_input,
            base_config_path=base_config,
            tuned_output_config_path=tuned_output_config,
            auto_tune=auto_tune,
            max_candidates=max_candidates,
        )
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=25) from exc
    except ValueError as exc:
        typer.echo(f"Invalid M3 finish input: {exc}", err=True)
        raise typer.Exit(code=26) from exc
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=27) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Unexpected M3 finish failure: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"M3 finish TTS input: {artifacts.tts_input_json}")
    typer.echo(f"M3 selected config: {artifacts.selected_config_path}")
    typer.echo(f"M3 output: {artifacts.m3_artifacts.tts_output_json}")
    typer.echo(f"M3 QA report: {artifacts.m3_artifacts.qa_report_json}")
    typer.echo(f"M3 stitched preview: {artifacts.m3_artifacts.stitched_preview_wav}")
    typer.echo(f"M3 closure report: {artifacts.closure_report_json}")


@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address for local UI."),
    port: int = typer.Option(8765, "--port", help="Bind port for local UI."),
) -> None:
    """Run local UI for end-to-end dubbing workflow operations."""
    typer.echo(f"Video Translate UI starting at: http://{host}:{port}")
    run_ui_server(host, port)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
