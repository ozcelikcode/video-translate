from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from video_translate.config import TranslateConfig


class TranslationBackend(Protocol):
    name: str

    def translate_batch(
        self,
        texts: list[str],
        *,
        source_language: str,
        target_language: str,
        batch_size: int,
    ) -> list[str]:
        """Translate a batch of texts."""


@dataclass(frozen=True)
class MockTranslationBackend:
    name: str = "mock"

    def translate_batch(
        self,
        texts: list[str],
        *,
        source_language: str,
        target_language: str,
        batch_size: int,
    ) -> list[str]:
        del source_language, target_language, batch_size
        # Deterministic placeholder backend for pipeline validation.
        return [text.strip() for text in texts]


@dataclass(frozen=True)
class TransformersTranslationBackend:
    model_id: str
    device: int
    max_new_tokens: int
    name: str = "transformers"

    def translate_batch(
        self,
        texts: list[str],
        *,
        source_language: str,
        target_language: str,
        batch_size: int,
    ) -> list[str]:
        del source_language, target_language
        if not texts:
            return []

        try:
            from transformers import pipeline  # Imported lazily.
        except ImportError as exc:
            raise RuntimeError(
                "Transformers backend requires 'transformers', 'sentencepiece', and 'torch'. "
                "Install with: pip install transformers sentencepiece torch"
            ) from exc

        translator = pipeline(
            task="translation",
            model=self.model_id,
            tokenizer=self.model_id,
            device=self.device,
        )
        results = translator(
            texts,
            batch_size=batch_size,
            max_new_tokens=self.max_new_tokens,
            clean_up_tokenization_spaces=True,
        )
        output: list[str] = []
        for item in results:
            if not isinstance(item, dict):
                raise ValueError("Unexpected translation output shape from transformers pipeline.")
            translated = item.get("translation_text")
            output.append(str(translated).strip())
        return output


def build_translation_backend(config: TranslateConfig) -> TranslationBackend:
    backend_name = config.backend.lower().strip()
    if backend_name == "mock":
        return MockTranslationBackend()
    if backend_name == "transformers":
        return TransformersTranslationBackend(
            model_id=config.transformers.model_id,
            device=config.transformers.device,
            max_new_tokens=config.transformers.max_new_tokens,
        )
    raise ValueError(
        f"Unsupported translation backend '{config.backend}'. "
        "Supported backends: mock, transformers."
    )
