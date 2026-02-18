import json
from pathlib import Path

from video_translate.pipeline.m3_finalize import finalize_m3_profile_selection


def test_finalize_m3_profile_selection_copies_recommended_profile(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    benchmark_json = run_root / "benchmarks" / "m3_profile_benchmark.json"
    source_config = tmp_path / "profiles" / "gtx1650_espeak.toml"
    source_config.parent.mkdir(parents=True, exist_ok=True)
    source_config.write_text("[tts]\nbackend='espeak'\n", encoding="utf-8")
    benchmark_json.parent.mkdir(parents=True, exist_ok=True)
    benchmark_json.write_text(
        json.dumps(
            {
                "stage": "m3_benchmark",
                "profiles": [
                    {
                        "profile_name": "gtx1650_espeak",
                        "config_path": str(source_config),
                        "status": "ok",
                        "total_pipeline_seconds": 1.23,
                        "max_abs_duration_delta_seconds": 0.05,
                        "quality_flag_count": 0,
                        "quality_flags": [],
                        "postfit_padding_segments": 1,
                        "postfit_trim_segments": 0,
                        "postfit_total_padded_seconds": 0.3,
                        "postfit_total_trimmed_seconds": 0.0,
                    }
                ],
                "summary": {
                    "recommended_profile": "gtx1650_espeak",
                },
            }
        ),
        encoding="utf-8",
    )

    output_config = tmp_path / "configs" / "profiles" / "m3_recommended.toml"
    artifacts = finalize_m3_profile_selection(
        run_root=run_root,
        benchmark_report_json=benchmark_json,
        output_config_path=output_config,
    )

    assert artifacts.recommended_profile == "gtx1650_espeak"
    assert artifacts.output_config_path.exists()
    assert artifacts.output_config_path.read_text(encoding="utf-8") == source_config.read_text(
        encoding="utf-8"
    )
    report_payload = json.loads(artifacts.selection_report_json.read_text(encoding="utf-8"))
    assert report_payload["stage"] == "m3_profile_selection"
    assert report_payload["selection_metrics"]["quality_flag_count"] == 0
