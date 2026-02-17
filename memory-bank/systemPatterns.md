# System Patterns

## Mimari Yaklasim
Pipeline tabanli, moduler, asamali genisletilebilir bir mimari.

## Ana Bilesenler
- `ingest`: YouTube indirme, medya dogrulama, ses cikarma/normalize
- `asr`: Ingilizce konusmayi zaman damgali transkripte donusturme
- `segment`: Cumle/ifade bazli zaman bloklari olusturma
- `translate`: EN->TR ceviri ve terminoloji tutarliligi
- `tts`: Turkce ses uretimi
- `sync`: Sure esleme ve zaman hizalama
- `mix`: Kaynak medya ile dublaji birlestirme
- `qa`: Otomatik kalite kontrolleri ve raporlama

## M1 Uygulanan Akis
- `cli.run-m1` -> `pipeline.m1.run_m1_pipeline`
- `cli.doctor` -> `preflight.run_preflight`
- `ingest.youtube.download_youtube_source` ile kaynak medya indirme
- `ingest.audio.normalize_audio_for_asr` ile mono 16k WAV uretimi
- `asr.whisper.transcribe_audio` ile zaman damgali metin cikarma
- `io.write_transcript_json` ve `io.write_srt` ile cikti yazimi
- `qa.m1_report.build_m1_qa_report` ile kalite metrigi cikarma
- `io.write_json` ile run manifest yazimi
- ASR hata dayanimi: GPU OOM durumunda `asr.whisper` CPU fallback

## M2 Hazirlik Akisi
- `cli.prepare-m2` -> `pipeline.m2_prep.prepare_m2_translation_input`
- M1 transcript JSON'undan ceviri giris sozlesmesi uretimi
- Cikti: `output/translate/translation_input.en-tr.json`

## M2 Uygulanan Akis
- `cli.run-m2` -> `pipeline.m2.run_m2_pipeline`
- Ceviri backend secimi: `translate.backends.build_translation_backend`
- Desteklenen backendler: `mock`, `transformers`
- Ceviri cikti normalizasyonu: yaygin UTF-8 mojibake metinler icin onarim heuristigi
- Glossary yukleme ve ceviri sonrasi terim duzeltme: `translate.glossary`
- Hiz optimizasyonu: tekrar eden source segmentleri icin dedup + reuse
- Cikti: `output/translate/translation_output.en-tr.json`
- QA: `qa.m2_report.build_m2_qa_report`
- QA cikti: `output/qa/m2_qa_report.json`
- M2 QA kapsami:
  - uzunluk orani
  - terminal noktalama
  - glossary terim eslesmesi
  - uzun segment akicilik heuristikleri (terminal noktalama eksigi + asiri duraklama noktalama)
- M2 calisma manifesti: `run_m2_manifest.json` (timing + speed alanlari)
- M2 QA acceptance gate:
  - QA raporundaki `quality_flags` -> whitelist disinda kalanlar `blocked_flags`
  - `qa_fail_on_flags=true` ise pipeline `RuntimeError` ile durur
  - `run_m2_manifest.json` icinde `qa_gate` sonucu yazilir

## M2 Benchmark Akisi
- `cli.benchmark-m2` -> `pipeline.m2_benchmark.run_m2_profile_benchmark`
- Ayni translation input uzerinde coklu profil calistirma
- Cikti: `benchmarks/m2_profile_benchmark.json`
- Rapor: profil bazli status + sure + kalite flag + onerilen profil

## M3 Hazirlik Akisi
- `cli.prepare-m3` -> `pipeline.m3_prep.prepare_m3_tts_input`
- M2 translation output JSON'undan TTS giris sozlesmesi uretimi
- Cikti: `output/tts/tts_input.tr.json`

## M3 Uygulanan Akis
- `cli.run-m3` -> `pipeline.m3.run_m3_pipeline`
- TTS backend secimi: `tts.backends.build_tts_backend`
- Desteklenen backendler: `mock`, `espeak`
- `espeak` sure uyumu: hedef sureye yaklasmak icin adaptif hiz denemeleri (bounded retry)
- Segment bazli WAV ciktilari: `output/tts/segments/seg_XXXXXX.wav`
- Segment stitching preview cikti: `output/tts/tts_preview_stitched.<lang>.wav`
- Cikti: `output/tts/tts_output.tr.json`
- QA: `qa.m3_report.build_m3_qa_report`
- QA cikti: `output/qa/m3_qa_report.json`
- M3 QA kapsami:
  - sure toleransi delta kontrolu
  - bos hedef metin kontrolu
- M3 QA acceptance gate:
  - QA raporundaki `quality_flags` -> whitelist disinda kalanlar `blocked_flags`
  - `tts.qa_fail_on_flags=true` ise pipeline `RuntimeError` ile durur
  - `run_m3_manifest.json` icinde `qa_gate` sonucu yazilir

## M3 Contract Ozet
- M3 input stage: `m3_tts_input`
  - Segment alanlari: `id/start/end/duration/target_text/target_word_count`
- M3 output stage: `m3_tts_output`
  - Segment alanlari: `id/start/end/target_duration/synthesized_duration/duration_delta/target_text/audio_path`
- Bu sozlesmeler `src/video_translate/tts/contracts.py` icinde.

## Donanim Profili
- GTX1650 + i5-12500H + 16GB RAM icin profil:
  - `configs/profiles/gtx1650_i5_12500h.toml`
  - ASR: `small` + `cuda` + `int8_float16` + OOM fallback
  - M2: `transformers` backend, CPU ceviri (`device=-1`) ile stabil calisma
- GTX1650 hiz profili:
  - `configs/profiles/gtx1650_fast.toml`
  - ASR beam ve token ayarlari hiz odakli
- GTX1650 strict kalite profili:
  - `configs/profiles/gtx1650_strict.toml`
  - M2 QA gate acik (`translate.qa_fail_on_flags=true`)
  - M3 QA gate acik (`tts.qa_fail_on_flags=true`)
- GTX1650 espeak profili:
  - `configs/profiles/gtx1650_espeak.toml`
  - M3 backend: `espeak`
- Doctor: profilde `transformers` backend seciliyse M2 Python bagimliliklarini dogrular
  - profilde `tts.backend=espeak` seciliyse `espeak` binary'si dogrulanir

## Tasarim Prensipleri
- Tek sorumluluk ilkesi
- Saf fonksiyon + acik veri akisi
- Konfigurasyon ile yonetilen davranis
- Tekrarlanabilir calisma (ayni girdi -> benzer cikti)
- Hata yonetiminde erken ve acik basarisizlik

## Veri Akisi
- Girdi: video URL veya yerel medya
- Ara cikti: normalize ses, transkript, segment JSON, ceviri JSON, TTS wav parcalari
- Cikti: dublajli video, opsiyonel altyazi, kalite raporu

## Senkron Stratejisi
- Kaynak konusma zamanlari referans alinir.
- Hedef Turkce sesin sureleri segment penceresine uydurulur.
- Gerekirse hiz/pause ayarlariyla dogal ritim korunur.
- Dudak okuma/facial landmark kullanilmaz.

## Test Kalibi
- Birim test: her modulun cekirdek islevleri
- Entegrasyon test: uctan uca kisa ornek video
- Regresyon test: ornek veri seti ile kalite metrik karsilastirmasi
