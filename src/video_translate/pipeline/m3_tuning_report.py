from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def build_m3_tuning_report_markdown(
    *,
    run_root: Path,
    benchmark_report_json: Path | None = None,
    output_markdown_path: Path | None = None,
) -> Path:
    report_json = benchmark_report_json or (run_root / "benchmarks" / "m3_profile_benchmark.json")
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    if not report_json.exists():
        raise FileNotFoundError(f"M3 benchmark report JSON not found: {report_json}")

    payload = _read_json(report_json)
    stage = str(payload.get("stage", "")).strip()
    if stage != "m3_benchmark":
        raise ValueError("Expected stage 'm3_benchmark' in benchmark report.")

    profiles = payload.get("profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("Field 'profiles' must be a list.")
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    recommended = summary.get("recommended_profile")
    ranking = payload.get("ranking", [])
    if not isinstance(ranking, list):
        ranking = []

    lines = [
        "# M3 Tuning Report",
        "",
        f"- Run root: `{run_root}`",
        f"- Benchmark report: `{report_json}`",
        f"- Recommended profile: `{recommended}`" if recommended else "- Recommended profile: `None`",
        "",
        "## Profile Table",
        "",
        "| Profile | Status | Total (s) | Max |Delta| (s) | Flags | Postfit Seg (pad/trim) | Postfit Sec (pad/trim) | Notes |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]

    for item in profiles:
        if not isinstance(item, dict):
            continue
        profile_name = str(item.get("profile_name", "unknown"))
        status = str(item.get("status", "unknown"))
        total_seconds = item.get("total_pipeline_seconds")
        max_abs_delta = item.get("max_abs_duration_delta_seconds")
        quality_flag_count = item.get("quality_flag_count")
        postfit_padding_segments = item.get("postfit_padding_segments")
        postfit_trim_segments = item.get("postfit_trim_segments")
        postfit_total_padded_seconds = item.get("postfit_total_padded_seconds")
        postfit_total_trimmed_seconds = item.get("postfit_total_trimmed_seconds")
        error = item.get("error")

        total_text = f"{float(total_seconds):.3f}" if isinstance(total_seconds, (int, float)) else "-"
        delta_text = f"{float(max_abs_delta):.3f}" if isinstance(max_abs_delta, (int, float)) else "-"
        flags_text = str(quality_flag_count) if isinstance(quality_flag_count, int) else "-"
        seg_text = (
            f"{int(postfit_padding_segments)}/{int(postfit_trim_segments)}"
            if isinstance(postfit_padding_segments, int) and isinstance(postfit_trim_segments, int)
            else "-"
        )
        sec_text = (
            f"{float(postfit_total_padded_seconds):.3f}/{float(postfit_total_trimmed_seconds):.3f}"
            if isinstance(postfit_total_padded_seconds, (int, float))
            and isinstance(postfit_total_trimmed_seconds, (int, float))
            else "-"
        )
        note_text = str(error) if error else ""
        lines.append(
            f"| {profile_name} | {status} | {total_text} | {delta_text} | {flags_text} | {seg_text} | {sec_text} | {note_text} |"
        )

    lines.extend(
        [
            "",
            "## Ranking",
            "",
            ", ".join(f"`{name}`" for name in ranking) if ranking else "No successful profile ranking.",
            "",
        ]
    )

    target_md = output_markdown_path or (run_root / "benchmarks" / "m3_tuning_report.md")
    target_md.parent.mkdir(parents=True, exist_ok=True)
    target_md.write_text("\n".join(lines), encoding="utf-8")
    return target_md
