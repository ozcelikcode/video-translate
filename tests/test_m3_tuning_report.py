import json
from pathlib import Path

from video_translate.pipeline.m3_tuning_report import build_m3_tuning_report_markdown


def test_build_m3_tuning_report_markdown(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    benchmark_json = run_root / "benchmarks" / "m3_profile_benchmark.json"
    benchmark_json.parent.mkdir(parents=True, exist_ok=True)
    benchmark_json.write_text(
        json.dumps(
            {
                "stage": "m3_benchmark",
                "run_root": str(run_root),
                "tts_input_json": str(run_root / "output" / "tts" / "tts_input.tr.json"),
                "profiles": [
                    {
                        "profile_name": "p_fast",
                        "status": "ok",
                        "total_pipeline_seconds": 1.2,
                        "max_abs_duration_delta_seconds": 0.03,
                        "quality_flag_count": 0,
                        "postfit_padding_segments": 0,
                        "postfit_trim_segments": 1,
                        "postfit_total_padded_seconds": 0.0,
                        "postfit_total_trimmed_seconds": 0.12,
                        "error": None,
                    },
                    {
                        "profile_name": "p_safe",
                        "status": "failed_preflight",
                        "total_pipeline_seconds": None,
                        "max_abs_duration_delta_seconds": None,
                        "quality_flag_count": None,
                        "error": "missing espeak",
                    },
                ],
                "ranking": ["p_fast"],
                "summary": {"recommended_profile": "p_fast"},
            }
        ),
        encoding="utf-8",
    )

    report_md = build_m3_tuning_report_markdown(run_root=run_root)
    assert report_md.exists()
    text = report_md.read_text(encoding="utf-8")
    assert "# M3 Tuning Report" in text
    assert "`p_fast`" in text
    assert "0/1" in text
    assert "missing espeak" in text
