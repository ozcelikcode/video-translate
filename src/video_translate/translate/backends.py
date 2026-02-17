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
    source_lang_code: str | None
    target_lang_code: str | None
    name: str = "transformers"

    @staticmethod
    def _repair_common_mojibake(text: str) -> str:
        # Common UTF-8 mis-decoding repair for Turkish text.
        if not text:
            return text

        suspicious_markers = ("Ã", "Ä", "Å", "Â", "?")
        if all(marker not in text for marker in suspicious_markers):
            return text

        def score(candidate: str) -> tuple[int, int]:
            suspicious_hits = sum(candidate.count(ch) for ch in suspicious_markers)
            turkish_hits = sum(candidate.count(ch) for ch in "çgiösüÇGIÖSÜ")
            return suspicious_hits, -turkish_hits

        best = text
        best_score = score(text)
        frontier = [text]
        seen = {text}

        for _ in range(3):
            next_frontier: list[str] = []
            for current in frontier:
                for source_encoding in ("latin-1", "cp1252", "cp1254"):
                    try:
                        repaired = current.encode(source_encoding).decode("utf-8")
                    except UnicodeError:
                        continue
                    if repaired in seen:
                        continue
                    seen.add(repaired)
                    next_frontier.append(repaired)
                    repaired_score = score(repaired)
                    if repaired_score < best_score:
                        best = repaired
                        best_score = repaired_score
            if not next_frontier:
                break
            frontier = next_frontier

        return best

    def translate_batch(
        self,
        texts: list[str],
        *,
        source_language: str,
        target_language: str,
        batch_size: int,
    ) -> list[str]:
        if not texts:
            return []

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Transformers backend requires 'transformers', 'sentencepiece', and 'torch'. "
                "Install with: pip install transformers sentencepiece torch"
            ) from exc

        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id)

        source_lang = self.source_lang_code or source_language
        target_lang = self.target_lang_code or target_language

        forced_bos_token_id: int | None = None
        if hasattr(tokenizer, "lang_code_to_id") and isinstance(tokenizer.lang_code_to_id, dict):
            if source_lang in tokenizer.lang_code_to_id and hasattr(tokenizer, "src_lang"):
                tokenizer.src_lang = source_lang
            if target_lang in tokenizer.lang_code_to_id:
                forced_bos_token_id = int(tokenizer.lang_code_to_id[target_lang])
        elif hasattr(tokenizer, "get_lang_id"):
            get_lang_id = getattr(tokenizer, "get_lang_id")
            if callable(get_lang_id):
                try:
                    forced_bos_token_id = int(get_lang_id(target_lang))
                    if hasattr(tokenizer, "src_lang"):
                        tokenizer.src_lang = source_lang
                except Exception:
                    forced_bos_token_id = None

        if self.device >= 0 and torch.cuda.is_available():
            model = model.to(f"cuda:{self.device}")
        else:
            model = model.to("cpu")

        outputs: list[str] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
            encoded = {key: value.to(model.device) for key, value in encoded.items()}
            generate_kwargs = {"max_new_tokens": self.max_new_tokens}
            if forced_bos_token_id is not None:
                generate_kwargs["forced_bos_token_id"] = forced_bos_token_id
            generated = model.generate(**encoded, **generate_kwargs)
            decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
            outputs.extend(self._repair_common_mojibake(text.strip()) for text in decoded)
        return outputs


def build_translation_backend(config: TranslateConfig) -> TranslationBackend:
    backend_name = config.backend.lower().strip()
    if backend_name == "mock":
        return MockTranslationBackend()
    if backend_name == "transformers":
        return TransformersTranslationBackend(
            model_id=config.transformers.model_id,
            device=config.transformers.device,
            max_new_tokens=config.transformers.max_new_tokens,
            source_lang_code=config.transformers.source_lang_code,
            target_lang_code=config.transformers.target_lang_code,
        )
    raise ValueError(
        f"Unsupported translation backend '{config.backend}'. "
        "Supported backends: mock, transformers."
    )

