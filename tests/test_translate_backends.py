import pytest

from video_translate.config import TranslateConfig, TranslateTransformersConfig
from video_translate.translate.backends import TransformersTranslationBackend, build_translation_backend


def _base_translate_config(backend: str) -> TranslateConfig:
    return TranslateConfig(
        backend=backend,
        source_language="en",
        target_language="tr",
        batch_size=8,
        min_length_ratio=0.5,
        max_length_ratio=1.8,
        glossary_path=None,
        glossary_case_sensitive=False,
        apply_glossary_postprocess=True,
        qa_check_terminal_punctuation=True,
        qa_check_long_segment_fluency=True,
        qa_long_segment_word_threshold=14,
        qa_long_segment_max_pause_punct=3,
        qa_fail_on_flags=False,
        qa_allowed_flags=(),
        transformers=TranslateTransformersConfig(
            model_id="facebook/m2m100_418M",
            device=-1,
            max_new_tokens=256,
            source_lang_code=None,
            target_lang_code=None,
        ),
    )


def test_build_translation_backend_mock() -> None:
    backend = build_translation_backend(_base_translate_config("mock"))
    translated = backend.translate_batch(
        ["hello world", " test "],
        source_language="en",
        target_language="tr",
        batch_size=8,
    )
    assert translated == ["hello world", "test"]


def test_build_translation_backend_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unsupported translation backend"):
        build_translation_backend(_base_translate_config("invalid"))


def test_repair_common_mojibake_for_turkish_text() -> None:
    broken = "Do\u00c4\u0178ru, bu s\u00c3\u00b6ylemek i\u00c3\u00a7in \u00c3\u00b6rnek bir c\u00c3\u00bcmle."
    repaired = TransformersTranslationBackend._repair_common_mojibake(broken)
    assert repaired == "Do\u011fru, bu s\u00f6ylemek i\u00e7in \u00f6rnek bir c\u00fcmle."


def test_repair_common_mojibake_cp1254_variant() -> None:
    broken = (
        "DoÃ„Å¸ru, bu yÃƒÂ¼zden burada elefantlarÃ„Â±n ÃƒÂ¶nÃƒÂ¼ndeyiz "
        "ve bu erkekler hakkÃ„Â±nda soÃ„Å¸uk Ã…Å¸ey."
    )
    repaired = TransformersTranslationBackend._repair_common_mojibake(broken)
    assert "Ã" not in repaired
    assert "Ä" not in repaired
    assert "\u015f" in repaired
    assert "\u0131" in repaired

