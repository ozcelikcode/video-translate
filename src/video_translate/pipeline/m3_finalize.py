from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class M3FinalizationArtifacts:
    source_config_path: Path
    output_config_path: Path
    selection_report_json: Path
    recommended_profile: str


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def finalize_m3_profile_selection(
    *,
    run_root: Path,
    benchmark_report_json: Path | None = None,
    output_config_path: Path | None = None,
) -> M3FinalizationArtifacts:
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    benchmark_json = benchmark_report_json or (run_root / "benchmarks" / "m3_profile_benchmark.json")
    if not benchmark_json.exists():
        raise FileNotFoundError(f"M3 benchmark report JSON not found: {benchmark_json}")

    payload = _read_json(benchmark_json)
    if str(payload.get("stage", "")).strip() != "m3_benchmark":
        raise ValueError("Expected stage 'm3_benchmark' in benchmark report.")

    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("Field 'summary' must be an object.")
    recommended_profile = str(summary.get("recommended_profile", "")).strip()
    if not recommended_profile:
        raise ValueError("No recommended profile in benchmark summary.")

    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("Field 'profiles' must be a list.")
    selected: dict[str, Any] | None = None
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        if str(profile.get("profile_name", "")).strip() == recommended_profile:
            selected = profile
            break
    if selected is None:
        raise ValueError(f"Recommended profile '{recommended_profile}' not found in profile list.")

    source_config_raw = str(selected.get("config_path", "")).strip()
    if not source_config_raw:
        raise ValueError(f"config_path missing for profile '{recommended_profile}'.")
    source_config_path = Path(source_config_raw)
    if not source_config_path.exists():
        raise FileNotFoundError(f"Recommended config path not found: {source_config_path}")

    target_config = output_config_path or (Path("configs") / "profiles" / "m3_recommended.toml")
    target_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_config_path, target_config)

    selection_report = run_root / "benchmarks" / "m3_profile_selection.json"
    selection_payload = {
        "stage": "m3_profile_selection",
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "run_root": str(run_root),
        "benchmark_report_json": str(benchmark_json),
        "recommended_profile": recommended_profile,
        "source_config_path": str(source_config_path),
        "output_config_path": str(target_config),
        "selection_metrics": {
            "status": selected.get("status"),
            "total_pipeline_seconds": selected.get("total_pipeline_seconds"),
            "max_abs_duration_delta_seconds": selected.get("max_abs_duration_delta_seconds"),
            "quality_flag_count": selected.get("quality_flag_count"),
            "quality_flags": selected.get("quality_flags"),
            "postfit_padding_segments": selected.get("postfit_padding_segments"),
            "postfit_trim_segments": selected.get("postfit_trim_segments"),
            "postfit_total_padded_seconds": selected.get("postfit_total_padded_seconds"),
            "postfit_total_trimmed_seconds": selected.get("postfit_total_trimmed_seconds"),
        },
    }
    selection_report.write_text(json.dumps(selection_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return M3FinalizationArtifacts(
        source_config_path=source_config_path,
        output_config_path=target_config,
        selection_report_json=selection_report,
        recommended_profile=recommended_profile,
    )
