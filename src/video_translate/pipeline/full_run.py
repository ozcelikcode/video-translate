from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from video_translate.config import AppConfig
from video_translate.models import M1Artifacts
from video_translate.pipeline.m1 import run_m1_pipeline
from video_translate.pipeline.m2 import M2Artifacts, run_m2_pipeline
from video_translate.pipeline.m2_prep import prepare_m2_translation_input
from video_translate.pipeline.m3 import M3Artifacts, run_m3_pipeline
from video_translate.pipeline.m3_closure import run_m3_closure_workflow
from video_translate.pipeline.m3_prep import prepare_m3_tts_input
from video_translate.preflight import preflight_errors, run_preflight


@dataclass(frozen=True)
class FullRunArtifacts:
    run_root: Path
    m1_artifacts: M1Artifacts
    m2_artifacts: M2Artifacts
    m3_artifacts: M3Artifacts
    m3_closure_report_json: Path | None


def _ensure_non_mock_tts_backend_for_final_flow(backend_name: str) -> None:
    normalized = backend_name.strip().lower()
    if normalized == "mock":
        raise RuntimeError(
            "Final dubbing flow cannot run with tts.backend='mock'. "
            "Mock backend only produces test tones (beep). "
            "Use tts.backend='espeak' (for example configs/profiles/gtx1650_i5_12500h.toml)."
        )


def run_full_dub_pipeline(
    *,
    source_url: str,
    config: AppConfig,
    workspace_dir: Path | None = None,
    run_id: str | None = None,
    emit_srt: bool = True,
    target_lang: str | None = None,
    use_m3_closure: bool = False,
    base_config_path: Path = Path("configs/profiles/gtx1650_espeak.toml"),
    tuned_output_config_path: Path = Path("configs/profiles/m3_espeak_recommended.toml"),
    auto_tune: bool = True,
    max_candidates: int = 16,
) -> FullRunArtifacts:
    resolved_target_lang = (target_lang or config.translate.target_language).strip() or "tr"
    _ensure_non_mock_tts_backend_for_final_flow(config.tts.backend)

    preflight_report = run_preflight(
        yt_dlp_bin=config.tools.yt_dlp,
        ffmpeg_bin=config.tools.ffmpeg,
        translate_backend=config.translate.backend,
        tts_backend=config.tts.backend,
        espeak_bin=config.tts.espeak_bin,
        check_translate_backend=True,
        check_tts_backend=True,
    )
    issues = preflight_errors(preflight_report)
    if issues:
        raise RuntimeError("Preflight failed: " + " | ".join(issues))

    m1_artifacts = run_m1_pipeline(
        source_url=source_url,
        config=config,
        workspace_dir=workspace_dir,
        run_id=run_id,
        emit_srt=emit_srt,
        preflight_report=preflight_report,
    )
    run_root = m1_artifacts.run_root

    m2_input = run_root / "output" / "translate" / f"translation_input.en-{resolved_target_lang}.json"
    m2_output = run_root / "output" / "translate" / f"translation_output.en-{resolved_target_lang}.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m2_manifest = run_root / "run_m2_manifest.json"
    prepare_m2_translation_input(
        transcript_json_path=m1_artifacts.transcript_json,
        output_json_path=m2_input,
        target_language=resolved_target_lang,
    )
    m2_artifacts = run_m2_pipeline(
        translation_input_json_path=m2_input,
        output_json_path=m2_output,
        qa_report_json_path=m2_qa,
        run_manifest_json_path=m2_manifest,
        config=config,
        target_language_override=resolved_target_lang,
    )

    if use_m3_closure:
        m3_closure = run_m3_closure_workflow(
            run_root=run_root,
            target_lang=resolved_target_lang,
            translation_output_json=m2_artifacts.translation_output_json,
            base_config_path=base_config_path,
            tuned_output_config_path=tuned_output_config_path,
            auto_tune=auto_tune,
            max_candidates=max_candidates,
        )
        return FullRunArtifacts(
            run_root=run_root,
            m1_artifacts=m1_artifacts,
            m2_artifacts=m2_artifacts,
            m3_artifacts=m3_closure.m3_artifacts,
            m3_closure_report_json=m3_closure.closure_report_json,
        )

    m3_input = run_root / "output" / "tts" / f"tts_input.{resolved_target_lang}.json"
    m3_output = run_root / "output" / "tts" / f"tts_output.{resolved_target_lang}.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest = run_root / "run_m3_manifest.json"
    prepare_m3_tts_input(
        translation_output_json_path=m2_artifacts.translation_output_json,
        output_json_path=m3_input,
        target_language=resolved_target_lang,
    )
    m3_artifacts = run_m3_pipeline(
        tts_input_json_path=m3_input,
        output_json_path=m3_output,
        qa_report_json_path=m3_qa,
        run_manifest_json_path=m3_manifest,
        config=config,
    )
    return FullRunArtifacts(
        run_root=run_root,
        m1_artifacts=m1_artifacts,
        m2_artifacts=m2_artifacts,
        m3_artifacts=m3_artifacts,
        m3_closure_report_json=None,
    )
