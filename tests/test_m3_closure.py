import json
from pathlib import Path
from types import SimpleNamespace

from video_translate.pipeline.m3_closure import run_m3_closure_workflow


def test_run_m3_closure_workflow_with_auto_tune(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "run"
    run_root.mkdir(parents=True, exist_ok=True)
    translation_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    translation_output.parent.mkdir(parents=True, exist_ok=True)
    translation_output.write_text("{}", encoding="utf-8")

    tts_input = run_root / "output" / "tts" / "tts_input.tr.json"
    tuned_config = tmp_path / "m3_espeak_recommended.toml"
    tuned_config.write_text("[tts]\nbackend='espeak'\n", encoding="utf-8")
    selection_report = run_root / "benchmarks" / "m3_profile_selection.json"
    selection_report.parent.mkdir(parents=True, exist_ok=True)
    selection_report.write_text("{}", encoding="utf-8")
    m3_output = run_root / "output" / "tts" / "tts_output.tr.json"
    m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
    m3_manifest = run_root / "run_m3_manifest.json"
    m3_preview = run_root / "output" / "tts" / "tts_preview_stitched.tr.wav"

    monkeypatch.setattr(
        "video_translate.pipeline.m3_closure.prepare_m3_tts_input",
        lambda **_: tts_input,
    )
    monkeypatch.setattr(
        "video_translate.pipeline.m3_closure.run_m3_espeak_tuning_automation",
        lambda **_: SimpleNamespace(
            generated_config_paths=[Path("a.toml"), Path("b.toml")],
            benchmark_report_json=run_root / "benchmarks" / "espeak_tune" / "m3_espeak_tuning_benchmark.json",
            tuning_report_markdown=run_root / "benchmarks" / "espeak_tune" / "m3_espeak_tuning_report.md",
            recommended_profile="p1",
            recommended_config_path=tuned_config,
            selection_report_json=selection_report,
        ),
    )
    monkeypatch.setattr(
        "video_translate.pipeline.m3_closure.load_config",
        lambda *_: SimpleNamespace(
            tools=SimpleNamespace(),
            pipeline=SimpleNamespace(),
            asr=SimpleNamespace(),
            translate=SimpleNamespace(),
            tts=SimpleNamespace(
                backend="espeak",
                sample_rate=24000,
                min_segment_seconds=0.12,
                mock_base_tone_hz=220,
                espeak_bin="espeak",
                espeak_voice="tr",
                espeak_speed_wpm=165,
                espeak_pitch=50,
                espeak_adaptive_rate_enabled=True,
                espeak_adaptive_rate_min_wpm=120,
                espeak_adaptive_rate_max_wpm=260,
                espeak_adaptive_rate_max_passes=3,
                espeak_adaptive_rate_tolerance_seconds=0.06,
                max_duration_delta_seconds=0.08,
                qa_max_postfit_segment_ratio=0.60,
                qa_max_postfit_seconds_ratio=0.35,
                qa_fail_on_flags=False,
                qa_allowed_flags=(),
            ),
        ),
    )

    captured = {"strict_gate": False}

    def _fake_run_m3_pipeline(*, config, **_kwargs):
        captured["strict_gate"] = bool(config.tts.qa_fail_on_flags)
        m3_output.parent.mkdir(parents=True, exist_ok=True)
        m3_output.write_text("{}", encoding="utf-8")
        m3_qa.parent.mkdir(parents=True, exist_ok=True)
        m3_qa.write_text("{}", encoding="utf-8")
        m3_manifest.write_text("{}", encoding="utf-8")
        m3_preview.parent.mkdir(parents=True, exist_ok=True)
        m3_preview.write_bytes(b"")
        return SimpleNamespace(
            tts_output_json=m3_output,
            qa_report_json=m3_qa,
            run_manifest_json=m3_manifest,
            stitched_preview_wav=m3_preview,
        )

    monkeypatch.setattr("video_translate.pipeline.m3_closure.run_m3_pipeline", _fake_run_m3_pipeline)

    artifacts = run_m3_closure_workflow(
        run_root=run_root,
        translation_output_json=translation_output,
        base_config_path=tmp_path / "base.toml",
        tuned_output_config_path=tuned_config,
        auto_tune=True,
        max_candidates=8,
    )

    assert artifacts.closure_report_json.exists()
    payload = json.loads(artifacts.closure_report_json.read_text(encoding="utf-8"))
    assert payload["stage"] == "m3_closure"
    assert payload["strict_tts_gate_enabled"] is True
    assert payload["tuning"]["candidate_count"] == 2
    assert captured["strict_gate"] is True
