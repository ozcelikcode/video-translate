import json
from pathlib import Path

from video_translate.ingest.subtitles import build_normalized_subtitle_payload, parse_subtitle_file


def test_parse_subtitle_file_parses_vtt_and_cleans_tags(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "sample.en.vtt"
    subtitle_path.write_text(
        "\n".join(
            [
                "WEBVTT",
                "",
                "00:00:00.000 --> 00:00:01.200",
                "<c.colorE5E5E5>Hello</c> <b>world</b>",
                "",
                "00:00:01.300 --> 00:00:02.000",
                "Speaker: welcome",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cues = parse_subtitle_file(subtitle_path)
    assert len(cues) == 2
    assert cues[0]["text"] == "Hello world"
    assert cues[1]["text"] == "welcome"


def test_build_normalized_subtitle_payload_includes_manual_and_auto(tmp_path: Path) -> None:
    manual = tmp_path / "manual.vtt"
    auto = tmp_path / "auto.vtt"
    manual.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello\n", encoding="utf-8")
    auto.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n", encoding="utf-8")

    payload = build_normalized_subtitle_payload(manual_path=manual, auto_path=auto)
    assert payload["stage"] == "m1_subtitles_normalized"
    assert payload["manual"]["cue_count"] == 1
    assert payload["auto"]["cue_count"] == 1
    json.dumps(payload)  # serializable

