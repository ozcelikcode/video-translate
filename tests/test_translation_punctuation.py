from video_translate.translate.punctuation import build_tts_render_text, restore_target_punctuation


def test_restore_target_punctuation_adds_terminal_from_source() -> None:
    target, hints = restore_target_punctuation(
        source_text="Hello world!",
        target_text="merhaba dunya",
    )
    assert target.endswith("!")
    assert hints["terminal_restored"] is True


def test_build_tts_render_text_forces_terminal_for_readability() -> None:
    tts_text, hints = build_tts_render_text(
        target_text="merhaba dunya",
        source_text="hello world",
    )
    assert tts_text.endswith(".")
    assert hints["tts_terminal_forced"] is True

