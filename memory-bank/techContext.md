# Tech Context

## Dil ve Araclar
- `Python 3.12+`
- `ffmpeg` (medya isleme)
- `yt-dlp` (YouTube indirme)
- `faster-whisper` veya esdeger acik ASR
- Yerel acik kaynak EN->TR ceviri modeli
- Yerel acik kaynak Turkce TTS modeli

## Gelistirme Araclari
- `pip` tabanli baslangic kurulum tanimlandi (`pip install -e .[dev]`)
- M2 opsiyonel bagimliliklari: `pip install -e .[m2]`
- `ruff` (lint + format)
- `mypy` (tip kontrolu)
- `pytest` (test)

## Teknik KisItlar
- Ucretli API yok
- Zorunlu bulut bagimliligi yok
- Donanim degiskenligi dusunulerek CPU/GPU uyumlu akis hedefi
- Uzun videolarda parca parca isleme desteklenmeli

## Konfigurasyon Ilkesi
- Calisma parametreleri kod icine gomulmeyecek.
- Ortam ve pipeline ayarlari tek konfigurasyon dosyasi uzerinden yonetilecek.
- Varsayilan ayarlar guvenli ve kalite odakli olacak.

## Cikti Standartlari
- Deterministik dosya klasor yapisi
- Ara ciktilarin acik adlandirilmasi
- Final artefaktlarin versiyonlanabilir olmasi

## Mevcut Uygulama Notlari
- CLI: `Typer`
- Konfigurasyon: `TOML` (`configs/default.toml`)
- ASR: `faster-whisper` (yerel model)
- Ingest: harici komutlar (`yt-dlp`, `ffmpeg`)
- On kontrol: `doctor` komutu ile yerel bagimlilik denetimi
- M2 hazirlik: `prepare-m2` ile ceviri giris sozlesmesi uretimi
- M2 calistirma: `run-m2` ile ceviri cikti + QA uretimi
- M2 benchmark: `benchmark-m2` ile profil karsilastirma
- M2 glossary: `configs/glossary.en-tr.json` (kaynak terim -> hedef terim)
- M2 QA: terminal noktalama, glossary eslesme ve uzun segment akicilik metrikleri
- M2 QA long-segment config:
  - `translate.qa_check_long_segment_fluency`
  - `translate.qa_long_segment_word_threshold`
  - `translate.qa_long_segment_max_pause_punct`
- M2 QA gate config:
  - `translate.qa_fail_on_flags`
  - `translate.qa_allowed_flags`
- Donanim profili: `configs/profiles/gtx1650_i5_12500h.toml`
- Donanim hiz profili: `configs/profiles/gtx1650_fast.toml`
- Donanim strict kalite profili: `configs/profiles/gtx1650_strict.toml`
- Donanim espeak profili: `configs/profiles/gtx1650_espeak.toml`
- ASR fallback: GPU OOM algilanirsa CPU (`int8`) fallback
- Doctor kontrolu: `transformers/sentencepiece/torch` bagimliliklarini da denetler
- M2 run manifest: `run_m2_manifest.json` icinde hiz/sure olcumleri
- M2 run manifest: `run_m2_manifest.json` icinde `qa_gate` sonucu da bulunur
- Benchmark raporu: `benchmarks/m2_profile_benchmark.json`
- M2 varsayilan model: `facebook/m2m100_418M`
- M2 ceviri cikti katmaninda UTF-8 mojibake onarim heuristigi aktif
- M3 hazirlik: `prepare-m3` ile TTS input sozlesmesi uretimi
- M3 calistirma: `run-m3` ile TTS cikti + QA uretimi
- M3 backend: `mock` ve `espeak` (yerel, API'siz)
- M3 backend modulu: `src/video_translate/tts/backends.py`
- M3 contract modulu: `src/video_translate/tts/contracts.py`
- M3 `espeak` adaptif hiz config alanlari:
  - `tts.espeak_adaptive_rate_enabled`
  - `tts.espeak_adaptive_rate_min_wpm`
  - `tts.espeak_adaptive_rate_max_wpm`
  - `tts.espeak_adaptive_rate_max_passes`
  - `tts.espeak_adaptive_rate_tolerance_seconds`
- M3 stitched preview artefakti:
  - `output/tts/tts_preview_stitched.<lang>.wav`
- M3 run manifest `outputs` alaninda `stitched_preview_wav` bulunur
- M3 config:
  - `tts.backend`
  - `tts.sample_rate`
  - `tts.min_segment_seconds`
  - `tts.mock_base_tone_hz`
  - `tts.espeak_bin`
  - `tts.espeak_voice`
  - `tts.espeak_speed_wpm`
  - `tts.espeak_pitch`
  - `tts.max_duration_delta_seconds`
  - `tts.qa_fail_on_flags`
  - `tts.qa_allowed_flags`
- M3 run manifest: `run_m3_manifest.json`
- Son tam test sonucu: `47 passed` (2026-02-17)

## Handoff Teknik Notlari
- M3 icin harici API kullanilmiyor; mevcut backend tamamen yerel dosya uretimi yapiyor.
- `doctor` komutu `tts.backend=espeak` oldugunda `espeak` binary denetimi yapiyor.
- M3 QA gate M2 ile ayni prensipte:
  - whitelist disi `quality_flags` varsa ve gate aktifse run fail.
- Son test kapsaminda M3 prep/pipeline/qa unit testleri var:
  - `tests/test_tts_backends.py`
  - `tests/test_m3_prep.py`
  - `tests/test_m3_pipeline.py`
  - `tests/test_m3_qa_report.py`
