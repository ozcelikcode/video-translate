import pytest

from video_translate.config import TranslateConfig, TranslateTransformersConfig
from video_translate.translate.backends import build_translation_backend


def _base_translate_config(backend: str) -> TranslateConfig:
    return TranslateConfig(
        backend=backend,
        source_language="en",
        target_language="tr",
        batch_size=8,
        min_length_ratio=0.5,
        max_length_ratio=1.8,
        transformers=TranslateTransformersConfig(
            model_id="Helsinki-NLP/opus-mt-en-tr",
            device=-1,
            max_new_tokens=256,
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
