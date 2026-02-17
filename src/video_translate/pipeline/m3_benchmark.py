from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_translate.config import load_config
from video_translate.pipeline.m3 import M3Artifacts, run_m3_pipeline
from video_translate.preflight import preflight_errors, run_preflight


@dataclass(frozen=True)
class M3BenchmarkResult:
    profile_name: str
    config_path: Path
    status: str
    output_json: Path | None
    qa_report_json: Path | None
    run_manifest_json: Path | None
    stitched_preview_wav: Path | None
    total_pipeline_seconds: float | None
    max_abs_duration_delta_seconds: float | None
    quality_flag_count: int | None
    quality_flags: list[str]
    error: str | None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _slug(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
    return normalized.lower() or "profile"


def _profile_name_from_path(config_path: Path) -> str:
    return config_path.stem


def run_m3_profile_benchmark(
    *,
    run_root: Path,
    tts_input_json: Path,
    config_paths: list[Path],
) -> Path:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not tts_input_json.exists():
        raise FileNotFoundError(f"TTS input JSON not found: {tts_input_json}")
    if not config_paths:
        raise ValueError("At least one config path is required for benchmark.")

    benchmark_dir = run_root / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results: list[M3BenchmarkResult] = []
    profile_counts: dict[str, int] = {}

    for config_path in config_paths:
        config = load_config(config_path)
        profile_name = _profile_name_from_path(config_path)
        count = profile_counts.get(profile_name, 0) + 1
        profile_counts[profile_name] = count
        profile_label = profile_name if count == 1 else f"{profile_name}_{count}"
        profile_slug = _slug(profile_label)

        preflight = run_preflight(
            yt_dlp_bin=config.tools.yt_dlp,
            ffmpeg_bin=config.tools.ffmpeg,
            translate_backend=config.translate.backend,
            tts_backend=config.tts.backend,
            espeak_bin=config.tts.espeak_bin,
            check_translate_backend=False,
            check_tts_backend=True,
        )
        issues = preflight_errors(preflight)
        if issues:
            results.append(
                M3BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="failed_preflight",
                    output_json=None,
                    qa_report_json=None,
                    run_manifest_json=None,
                    stitched_preview_wav=None,
                    total_pipeline_seconds=None,
                    max_abs_duration_delta_seconds=None,
                    quality_flag_count=None,
                    quality_flags=[],
                    error="; ".join(issues),
                )
            )
            continue

        output_json = run_root / "output" / "tts" / f"tts_output.{profile_slug}.json"
        qa_json = run_root / "output" / "qa" / f"m3_qa_report.{profile_slug}.json"
        manifest_json = benchmark_dir / f"run_m3_manifest.{profile_slug}.json"

        try:
            artifacts: M3Artifacts = run_m3_pipeline(
                tts_input_json_path=tts_input_json,
                output_json_path=output_json,
                qa_report_json_path=qa_json,
                run_manifest_json_path=manifest_json,
                config=config,
            )
            manifest_payload = _read_json(artifacts.run_manifest_json)
            qa_payload = _read_json(artifacts.qa_report_json)
            timings_payload = manifest_payload.get("timings_seconds", {})
            duration_payload = qa_payload.get("duration_metrics", {})
            total_pipeline_seconds = float(timings_payload.get("total_pipeline", 0.0))
            max_abs_delta = float(duration_payload.get("max_abs_delta_seconds", 0.0))
            quality_flags_raw = qa_payload.get("quality_flags", [])
            if not isinstance(quality_flags_raw, list):
                quality_flags_raw = []
            quality_flags = [str(flag) for flag in quality_flags_raw]
            results.append(
                M3BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="ok",
                    output_json=artifacts.tts_output_json,
                    qa_report_json=artifacts.qa_report_json,
                    run_manifest_json=artifacts.run_manifest_json,
                    stitched_preview_wav=_copy_preview_for_profile(
                        artifacts.stitched_preview_wav,
                        benchmark_dir=benchmark_dir,
                        profile_slug=profile_slug,
                    ),
                    total_pipeline_seconds=total_pipeline_seconds,
                    max_abs_duration_delta_seconds=max_abs_delta,
                    quality_flag_count=len(quality_flags),
                    quality_flags=quality_flags,
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                M3BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="failed_run",
                    output_json=output_json if output_json.exists() else None,
                    qa_report_json=qa_json if qa_json.exists() else None,
                    run_manifest_json=manifest_json if manifest_json.exists() else None,
                    stitched_preview_wav=None,
                    total_pipeline_seconds=None,
                    max_abs_duration_delta_seconds=None,
                    quality_flag_count=None,
                    quality_flags=[],
                    error=str(exc),
                )
            )

    successful = [result for result in results if result.status == "ok"]
    ranked = sorted(
        successful,
        key=lambda item: (
            item.quality_flag_count if item.quality_flag_count is not None else 9999,
            item.max_abs_duration_delta_seconds
            if item.max_abs_duration_delta_seconds is not None
            else float("inf"),
            item.total_pipeline_seconds if item.total_pipeline_seconds is not None else float("inf"),
        ),
    )

    report_path = benchmark_dir / "m3_profile_benchmark.json"
    payload = {
        "stage": "m3_benchmark",
        "run_root": str(run_root),
        "tts_input_json": str(tts_input_json),
        "profiles": [
            {
                "profile_name": result.profile_name,
                "config_path": str(result.config_path),
                "status": result.status,
                "output_json": str(result.output_json) if result.output_json else None,
                "qa_report_json": str(result.qa_report_json) if result.qa_report_json else None,
                "run_manifest_json": str(result.run_manifest_json) if result.run_manifest_json else None,
                "stitched_preview_wav": (
                    str(result.stitched_preview_wav) if result.stitched_preview_wav else None
                ),
                "total_pipeline_seconds": result.total_pipeline_seconds,
                "max_abs_duration_delta_seconds": result.max_abs_duration_delta_seconds,
                "quality_flag_count": result.quality_flag_count,
                "quality_flags": result.quality_flags,
                "error": result.error,
            }
            for result in results
        ],
        "ranking": [result.profile_name for result in ranked],
        "summary": {
            "profile_count": len(results),
            "success_count": len(successful),
            "failed_count": len(results) - len(successful),
            "recommended_profile": ranked[0].profile_name if ranked else None,
        },
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _copy_preview_for_profile(source_preview_wav: Path, *, benchmark_dir: Path, profile_slug: str) -> Path:
    target = benchmark_dir / f"tts_preview_stitched.{profile_slug}.wav"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_preview_wav, target)
    return target
