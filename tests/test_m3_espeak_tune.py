import json
from pathlib import Path

from video_translate.pipeline.m3_espeak_tune import run_m3_espeak_tuning_automation


def test_run_m3_espeak_tuning_automation_generates_candidates_and_locks_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = tmp_path / "run"
    tts_input = run_root / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-18T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 1,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "target_text": "merhaba",
                        "target_word_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    base_config = tmp_path / "gtx1650_espeak.toml"
    base_config.write_text(
        "\n".join(
            [
                "[tts]",
                "backend = \"espeak\"",
                "espeak_speed_wpm = 165",
                "espeak_pitch = 50",
                "espeak_adaptive_rate_enabled = true",
                "espeak_adaptive_rate_min_wpm = 120",
                "espeak_adaptive_rate_max_wpm = 260",
                "espeak_adaptive_rate_max_passes = 3",
                "espeak_adaptive_rate_tolerance_seconds = 0.06",
                "qa_max_postfit_segment_ratio = 0.60",
                "qa_max_postfit_seconds_ratio = 0.35",
            ]
        ),
        encoding="utf-8",
    )

    def _fake_benchmark(*, run_root: Path, tts_input_json: Path, config_paths: list[Path]) -> Path:
        report = run_root / "benchmarks" / "m3_profile_benchmark.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        profile_name = config_paths[0].stem
        report.write_text(
            json.dumps(
                {
                    "stage": "m3_benchmark",
                    "profiles": [
                        {
                            "profile_name": profile_name,
                            "config_path": str(config_paths[0]),
                            "status": "ok",
                            "total_pipeline_seconds": 1.0,
                            "max_abs_duration_delta_seconds": 0.05,
                            "quality_flag_count": 0,
                            "quality_flags": [],
                            "postfit_padding_segments": 0,
                            "postfit_trim_segments": 0,
                            "postfit_total_padded_seconds": 0.0,
                            "postfit_total_trimmed_seconds": 0.0,
                            "error": None,
                        }
                    ],
                    "ranking": [profile_name],
                    "summary": {"recommended_profile": profile_name},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return report

    monkeypatch.setattr(
        "video_translate.pipeline.m3_espeak_tune.run_m3_profile_benchmark",
        _fake_benchmark,
    )

    output_config = tmp_path / "m3_espeak_recommended.toml"
    artifacts = run_m3_espeak_tuning_automation(
        run_root=run_root,
        tts_input_json=tts_input,
        base_config_path=base_config,
        output_config_path=output_config,
        max_candidates=5,
    )

    assert len(artifacts.generated_config_paths) == 5
    assert artifacts.benchmark_report_json.exists()
    assert artifacts.tuning_report_markdown.exists()
    assert artifacts.recommended_config_path.exists()
    assert artifacts.selection_report_json.exists()
