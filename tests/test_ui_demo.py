import json
from pathlib import Path

from video_translate.ui_demo import UIDemoRequest, execute_m3_demo


def test_execute_m3_demo_runs_prepare_and_m3(tmp_path: Path) -> None:
    run_root = tmp_path / "run_ui"
    translation_output = run_root / "output" / "translate" / "translation_output.en-tr.json"
    translation_output.parent.mkdir(parents=True, exist_ok=True)
    translation_output.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "stage": "m2_translation_output",
                "generated_at_utc": "2026-02-17T10:00:00Z",
                "backend": "mock",
                "source_language": "en",
                "target_language": "tr",
                "segment_count": 1,
                "total_source_word_count": 2,
                "total_target_word_count": 2,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 1.0,
                        "duration": 1.0,
                        "source_text": "hello world",
                        "target_text": "merhaba dunya",
                        "source_word_count": 2,
                        "target_word_count": 2,
                        "length_ratio": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = execute_m3_demo(
        UIDemoRequest(
            run_root=run_root,
            config_path=None,
            target_lang="tr",
            prepare_input=True,
            translation_output_json=translation_output,
            tts_input_json=None,
        )
    )

    assert result["ok"] is True
    artifacts = result["artifacts"]
    assert Path(artifacts["tts_input_json"]).exists()
    assert Path(artifacts["tts_output_json"]).exists()
    assert Path(artifacts["qa_report_json"]).exists()
    assert Path(artifacts["run_manifest_json"]).exists()
    assert Path(artifacts["stitched_preview_wav"]).exists()
    assert isinstance(result["segment_preview"], list)

