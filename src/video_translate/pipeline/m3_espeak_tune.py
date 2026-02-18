from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from itertools import product
from pathlib import Path

from video_translate.config import load_config
from video_translate.pipeline.m3_benchmark import run_m3_profile_benchmark
from video_translate.pipeline.m3_finalize import (
    M3FinalizationArtifacts,
    finalize_m3_profile_selection,
)
from video_translate.pipeline.m3_tuning_report import build_m3_tuning_report_markdown


@dataclass(frozen=True)
class M3EspeakTuningArtifacts:
    generated_config_paths: list[Path]
    benchmark_report_json: Path
    tuning_report_markdown: Path
    recommended_profile: str
    recommended_config_path: Path
    selection_report_json: Path


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _write_tts_override_config(path: Path, tts_values: dict[str, object]) -> None:
    lines = ["[tts]"]
    for key, value in tts_values.items():
        lines.append(f"{key} = {_format_toml_value(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_candidate_tts_overrides(
    *,
    speed_wpm: int,
    pitch: int,
    adaptive_passes: int,
    adaptive_tolerance: float,
    adaptive_min_wpm: int,
    adaptive_max_wpm: int,
    qa_max_postfit_segment_ratio: float,
    qa_max_postfit_seconds_ratio: float,
    max_candidates: int,
) -> list[dict[str, object]]:
    speed_values = sorted(
        {
            max(adaptive_min_wpm, min(adaptive_max_wpm, speed_wpm + delta))
            for delta in (-30, -20, -10, 0, 10, 20, 30)
        }
    )
    pitch_values = sorted({max(0, min(99, pitch + delta)) for delta in (-12, -6, 0, 6, 12)})
    pass_values = sorted({max(1, adaptive_passes - 1), adaptive_passes, min(8, adaptive_passes + 1)})
    tolerance_values = sorted(
        {
            max(0.02, adaptive_tolerance * 0.75),
            adaptive_tolerance,
            min(0.15, adaptive_tolerance * 1.25),
        }
    )
    raw_candidates: list[tuple[float, dict[str, object]]] = []
    for candidate_speed, candidate_pitch, candidate_passes, candidate_tolerance in product(
        speed_values, pitch_values, pass_values, tolerance_values
    ):
        distance = (
            abs(candidate_speed - speed_wpm) / 10.0
            + abs(candidate_pitch - pitch) / 6.0
            + abs(candidate_passes - adaptive_passes) * 0.8
            + abs(candidate_tolerance - adaptive_tolerance) / 0.02
        )
        raw_candidates.append(
            (
                distance,
                {
                    "backend": "espeak",
                    "espeak_voice": "tr",
                    "espeak_speed_wpm": candidate_speed,
                    "espeak_pitch": candidate_pitch,
                    "espeak_adaptive_rate_enabled": True,
                    "espeak_adaptive_rate_min_wpm": adaptive_min_wpm,
                    "espeak_adaptive_rate_max_wpm": adaptive_max_wpm,
                    "espeak_adaptive_rate_max_passes": candidate_passes,
                    "espeak_adaptive_rate_tolerance_seconds": round(candidate_tolerance, 3),
                    "qa_max_postfit_segment_ratio": qa_max_postfit_segment_ratio,
                    "qa_max_postfit_seconds_ratio": qa_max_postfit_seconds_ratio,
                },
            )
        )
    raw_candidates.sort(key=lambda item: item[0])
    selected: list[dict[str, object]] = []
    seen_keys: set[tuple[object, ...]] = set()
    for _, candidate in raw_candidates:
        identity = (
            candidate["espeak_speed_wpm"],
            candidate["espeak_pitch"],
            candidate["espeak_adaptive_rate_max_passes"],
            candidate["espeak_adaptive_rate_tolerance_seconds"],
        )
        if identity in seen_keys:
            continue
        seen_keys.add(identity)
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return selected


def run_m3_espeak_tuning_automation(
    *,
    run_root: Path,
    tts_input_json: Path,
    base_config_path: Path,
    output_config_path: Path,
    max_candidates: int = 16,
) -> M3EspeakTuningArtifacts:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not tts_input_json.exists():
        raise FileNotFoundError(f"TTS input JSON not found: {tts_input_json}")
    if max_candidates <= 0:
        raise ValueError("max_candidates must be > 0.")

    base_config = load_config(base_config_path)
    if base_config.tts.backend.strip().lower() != "espeak":
        raise ValueError("Base config must use tts.backend = 'espeak'.")

    candidates = _build_candidate_tts_overrides(
        speed_wpm=base_config.tts.espeak_speed_wpm,
        pitch=base_config.tts.espeak_pitch,
        adaptive_passes=base_config.tts.espeak_adaptive_rate_max_passes,
        adaptive_tolerance=base_config.tts.espeak_adaptive_rate_tolerance_seconds,
        adaptive_min_wpm=base_config.tts.espeak_adaptive_rate_min_wpm,
        adaptive_max_wpm=base_config.tts.espeak_adaptive_rate_max_wpm,
        qa_max_postfit_segment_ratio=base_config.tts.qa_max_postfit_segment_ratio,
        qa_max_postfit_seconds_ratio=base_config.tts.qa_max_postfit_seconds_ratio,
        max_candidates=max_candidates,
    )
    tune_dir = run_root / "benchmarks" / "espeak_tune"
    config_dir = tune_dir / "configs"
    generated_paths: list[Path] = []
    for index, tts_override in enumerate(candidates, start=1):
        profile_name = (
            f"espeak_s{int(tts_override['espeak_speed_wpm'])}"
            f"_p{int(tts_override['espeak_pitch'])}"
            f"_m{int(tts_override['espeak_adaptive_rate_max_passes'])}"
            f"_t{str(tts_override['espeak_adaptive_rate_tolerance_seconds']).replace('.', '_')}"
        )
        config_path = config_dir / f"{index:02d}_{profile_name}.toml"
        _write_tts_override_config(config_path, tts_override)
        generated_paths.append(config_path)

    benchmark_report = run_m3_profile_benchmark(
        run_root=run_root,
        tts_input_json=tts_input_json,
        config_paths=generated_paths,
    )
    tuned_benchmark_report = tune_dir / "m3_espeak_tuning_benchmark.json"
    tuned_benchmark_report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(benchmark_report, tuned_benchmark_report)

    tuning_report = build_m3_tuning_report_markdown(
        run_root=run_root,
        benchmark_report_json=tuned_benchmark_report,
        output_markdown_path=tune_dir / "m3_espeak_tuning_report.md",
    )
    finalization: M3FinalizationArtifacts = finalize_m3_profile_selection(
        run_root=run_root,
        benchmark_report_json=tuned_benchmark_report,
        output_config_path=output_config_path,
    )

    meta_json = tune_dir / "m3_espeak_tuning_meta.json"
    meta_json.write_text(
        json.dumps(
            {
                "stage": "m3_espeak_tuning_automation",
                "run_root": str(run_root),
                "tts_input_json": str(tts_input_json),
                "base_config_path": str(base_config_path),
                "generated_config_count": len(generated_paths),
                "generated_config_paths": [str(path) for path in generated_paths],
                "benchmark_report_json": str(tuned_benchmark_report),
                "tuning_report_markdown": str(tuning_report),
                "recommended_profile": finalization.recommended_profile,
                "recommended_config_path": str(finalization.output_config_path),
                "selection_report_json": str(finalization.selection_report_json),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return M3EspeakTuningArtifacts(
        generated_config_paths=generated_paths,
        benchmark_report_json=tuned_benchmark_report,
        tuning_report_markdown=tuning_report,
        recommended_profile=finalization.recommended_profile,
        recommended_config_path=finalization.output_config_path,
        selection_report_json=finalization.selection_report_json,
    )
