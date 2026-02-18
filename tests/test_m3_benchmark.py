import json
from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch

from video_translate.pipeline.m3_benchmark import run_m3_profile_benchmark


def test_run_m3_profile_benchmark_writes_report(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    tts_input = run_root / "output" / "tts" / "tts_input.tr.json"
    tts_input.parent.mkdir(parents=True, exist_ok=True)
    tts_input.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m3_tts_input",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "language": "tr",
                "segment_count": 1,
                "total_target_word_count": 2,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "target_text": "merhaba dunya",
                        "target_word_count": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    config_a = tmp_path / "a.toml"
    config_b = tmp_path / "b.toml"
    config_a.write_text("[tts]\nbackend='mock'\n", encoding="utf-8")
    config_b.write_text("[tts]\nbackend='mock'\n", encoding="utf-8")

    monkeypatch.setattr(
        "video_translate.pipeline.m3_benchmark.run_preflight",
        lambda **_: SimpleNamespace(ok=True),
    )
    monkeypatch.setattr(
        "video_translate.pipeline.m3_benchmark.preflight_errors",
        lambda _: [],
    )

    report_path = run_m3_profile_benchmark(
        run_root=run_root,
        tts_input_json=tts_input,
        config_paths=[config_a, config_b],
    )

    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["stage"] == "m3_benchmark"
    assert payload["summary"]["profile_count"] == 2
    assert payload["summary"]["success_count"] == 2
    assert payload["summary"]["recommended_profile"] is not None
    assert "postfit_padding_segments" in payload["profiles"][0]
    assert "postfit_trim_segments" in payload["profiles"][0]
