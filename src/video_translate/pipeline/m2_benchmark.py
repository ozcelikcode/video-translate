from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from video_translate.config import load_config
from video_translate.pipeline.m2 import M2Artifacts, run_m2_pipeline
from video_translate.preflight import preflight_errors, run_preflight


@dataclass(frozen=True)
class M2BenchmarkResult:
    profile_name: str
    config_path: Path
    status: str
    output_json: Path | None
    qa_report_json: Path | None
    run_manifest_json: Path | None
    total_pipeline_seconds: float | None
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


def run_m2_profile_benchmark(
    *,
    run_root: Path,
    translation_input_json: Path,
    config_paths: list[Path],
) -> Path:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not translation_input_json.exists():
        raise FileNotFoundError(f"Translation input JSON not found: {translation_input_json}")
    if not config_paths:
        raise ValueError("At least one config path is required for benchmark.")

    benchmark_dir = run_root / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results: list[M2BenchmarkResult] = []
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
            check_translate_backend=True,
        )
        issues = preflight_errors(preflight)
        if issues:
            results.append(
                M2BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="failed_preflight",
                    output_json=None,
                    qa_report_json=None,
                    run_manifest_json=None,
                    total_pipeline_seconds=None,
                    quality_flag_count=None,
                    quality_flags=[],
                    error="; ".join(issues),
                )
            )
            continue

        output_json = run_root / "output" / "translate" / f"translation_output.{profile_slug}.json"
        qa_json = run_root / "output" / "qa" / f"m2_qa_report.{profile_slug}.json"
        manifest_json = benchmark_dir / f"run_m2_manifest.{profile_slug}.json"

        try:
            artifacts: M2Artifacts = run_m2_pipeline(
                translation_input_json_path=translation_input_json,
                output_json_path=output_json,
                qa_report_json_path=qa_json,
                run_manifest_json_path=manifest_json,
                config=config,
                target_language_override=config.translate.target_language,
            )
            manifest_payload = _read_json(artifacts.run_manifest_json)
            qa_payload = _read_json(artifacts.qa_report_json)
            timings_payload = manifest_payload.get("timings_seconds", {})
            total_pipeline_seconds = float(timings_payload.get("total_pipeline", 0.0))
            quality_flags_raw = qa_payload.get("quality_flags", [])
            if not isinstance(quality_flags_raw, list):
                quality_flags_raw = []
            quality_flags = [str(flag) for flag in quality_flags_raw]
            results.append(
                M2BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="ok",
                    output_json=artifacts.translation_output_json,
                    qa_report_json=artifacts.qa_report_json,
                    run_manifest_json=artifacts.run_manifest_json,
                    total_pipeline_seconds=total_pipeline_seconds,
                    quality_flag_count=len(quality_flags),
                    quality_flags=quality_flags,
                    error=None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                M2BenchmarkResult(
                    profile_name=profile_label,
                    config_path=config_path,
                    status="failed_run",
                    output_json=output_json if output_json.exists() else None,
                    qa_report_json=qa_json if qa_json.exists() else None,
                    run_manifest_json=manifest_json if manifest_json.exists() else None,
                    total_pipeline_seconds=None,
                    quality_flag_count=None,
                    quality_flags=[],
                    error=str(exc),
                )
            )

    successful = [result for result in results if result.status == "ok"]
    ranked = sorted(
        successful,
        key=lambda item: (
            item.total_pipeline_seconds if item.total_pipeline_seconds is not None else float("inf"),
            item.quality_flag_count if item.quality_flag_count is not None else 9999,
        ),
    )

    report_path = benchmark_dir / "m2_profile_benchmark.json"
    payload = {
        "stage": "m2_benchmark",
        "run_root": str(run_root),
        "translation_input_json": str(translation_input_json),
        "profiles": [
            {
                "profile_name": result.profile_name,
                "config_path": str(result.config_path),
                "status": result.status,
                "output_json": str(result.output_json) if result.output_json else None,
                "qa_report_json": str(result.qa_report_json) if result.qa_report_json else None,
                "run_manifest_json": str(result.run_manifest_json) if result.run_manifest_json else None,
                "total_pipeline_seconds": result.total_pipeline_seconds,
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
