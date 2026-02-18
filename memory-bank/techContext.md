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
- Uctan uca tek komut: `run-dub` (URL -> M1 -> M2 -> M3)
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
- M3 benchmark: `benchmark-m3` ile profil karsilastirma
- M3 tuning markdown raporu: `report-m3-tuning`
- M3 profil finalizasyonu: `finalize-m3-profile`
- M3 espeak otomatik tuning: `tune-m3-espeak`
- M3 kapanis otomasyonu: `finish-m3`
- M3 lokal UI demo: `ui-demo`
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
  - `tts.qa_max_postfit_segment_ratio`
  - `tts.qa_max_postfit_seconds_ratio`
  - `tts.qa_fail_on_flags`
  - `tts.qa_allowed_flags`
- M3 run manifest: `run_m3_manifest.json`
- M3 benchmark raporu: `benchmarks/m3_profile_benchmark.json`
- M3 tuning raporu: `benchmarks/m3_tuning_report.md`
- M3 finalizasyon raporu: `benchmarks/m3_profile_selection.json`
- M3 espeak tuning artefaktlari:
  - `benchmarks/espeak_tune/m3_espeak_tuning_benchmark.json`
  - `benchmarks/espeak_tune/m3_espeak_tuning_report.md`
  - `benchmarks/espeak_tune/m3_espeak_tuning_meta.json`
- M3 kapanis raporu:
  - `benchmarks/m3_closure_report.json`
- M3 kapanis modul adlandirmasi:
  - `src/video_translate/pipeline/m3_closure.py`
  - `tests/test_m3_closure.py`
- M3 benchmark/tuning post-fit metrikleri:
  - `postfit_padding_segments`
  - `postfit_trim_segments`
  - `postfit_total_padded_seconds`
  - `postfit_total_trimmed_seconds`
- UI demo dokumani: `docs/ui-demo.md`
- UI demo endpointleri:
  - `POST /run-youtube-dub`
  - `POST /run-m3`
- UI demo cache politikasi:
  - HTTP yanitlarinda `Cache-Control: no-store`
  - build etiketi: `2026-02-18-youtube-m3fit`
- M3 sure post-fit:
  - kisa kalan segment WAV'lerine sessizlik padding
  - run manifest: `duration_postfit` metrikleri
  - uzun kalan segment WAV'lerinde trim
- M3 QA post-fit guard:
  - post-fit segment/sure oranlari esik ustundeyse kalite bayragi uretir
- Windows startup script: `open_project.bat`
  - `.venv` olusturma + `pip install -e .[dev,m2]` + `doctor` + `ui-demo`
  - Opsiyonlar: `--skip-install`, `--no-ui`
- Son tam test sonucu: `63 passed` (2026-02-18)

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

