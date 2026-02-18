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

## Uctan Uca Tek Komut Akisi
- `cli.run-dub` -> `pipeline.full_run.run_full_dub_pipeline`
- Zincir:
  - preflight (M1+M2+M3 bagimlilik denetimi)
  - `run_m1_pipeline`
  - `prepare_m2_translation_input`
  - `run_m2_pipeline`
  - varsayilan: `prepare_m3_tts_input` + `run_m3_pipeline`
  - opsiyonel: `--m3-closure` ile `run_m3_closure_workflow`

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
- Sure post-fit: hedef sÃ¼reden kisa kalan segmentlere WAV sonuna sessizlik padding
- Segment stitching preview cikti: `output/tts/tts_preview_stitched.<lang>.wav`
- Cikti: `output/tts/tts_output.tr.json`
- QA: `qa.m3_report.build_m3_qa_report`
- QA cikti: `output/qa/m3_qa_report.json`
- M3 QA kapsami:
  - sure toleransi delta kontrolu
  - bos hedef metin kontrolu
  - post-fit mudahale yogunlugu kontrolu (segment orani + sure orani)
- M3 QA acceptance gate:
  - QA raporundaki `quality_flags` -> whitelist disinda kalanlar `blocked_flags`
  - `tts.qa_fail_on_flags=true` ise pipeline `RuntimeError` ile durur
  - `run_m3_manifest.json` icinde `qa_gate` sonucu yazilir
- M3 run manifest ek alani:
  - `duration_postfit.silence_padding_applied_segments`
  - `duration_postfit.total_padded_seconds`
  - `duration_postfit.trim_applied_segments`
  - `duration_postfit.total_trimmed_seconds`
- M3 QA yeni bayraklar:
  - `postfit_segment_ratio_above_max`
  - `postfit_seconds_ratio_above_max`

## M3 Benchmark Akisi
- `cli.benchmark-m3` -> `pipeline.m3_benchmark.run_m3_profile_benchmark`
- Ayni `tts_input` uzerinde coklu profil calistirma
- Cikti: `benchmarks/m3_profile_benchmark.json`
- Rapor: profil bazli status + sure + max sure sapmasi + kalite flag + onerilen profil
- Rapor ayrica post-fit etkisini tasir:
  - `postfit_padding_segments`, `postfit_trim_segments`
  - `postfit_total_padded_seconds`, `postfit_total_trimmed_seconds`
- Benchmark icin stitched preview dosyalari profil bazli ayrilir:
  - `benchmarks/tts_preview_stitched.<profile>.wav`

## M3 Tuning Raporu Akisi
- `cli.report-m3-tuning` -> `pipeline.m3_tuning_report.build_m3_tuning_report_markdown`
- Girdi: `benchmarks/m3_profile_benchmark.json`
- Cikti: `benchmarks/m3_tuning_report.md`
- Rapor icerigi: onerilen profil + profil bazli markdown tablo + ranking
- Tuning tablosu post-fit segment/sure etkisini de gosterir.

## M3 Finalizasyon Akisi
- `cli.finalize-m3-profile` -> `pipeline.m3_finalize.finalize_m3_profile_selection`
- Girdi: `benchmarks/m3_profile_benchmark.json`
- Cikti:
  - `configs/profiles/m3_recommended.toml` (veya `--output-config`)
  - `benchmarks/m3_profile_selection.json`
- Amac: benchmark'ta onerilen profili sabitleyip M3 kapanisinda tekrar edilebilir profil secimi saglamak.

## M3 Espeak Otomatik Tuning Akisi
- `cli.tune-m3-espeak` -> `pipeline.m3_espeak_tune.run_m3_espeak_tuning_automation`
- Zincir:
  - espeak aday profil override dosyalari uretimi
  - `benchmark-m3` calistirma
  - `report-m3-tuning` markdown uretimi
  - `finalize-m3-profile` ile onerilen profili kilitleme
- Ciktilar:
  - `benchmarks/espeak_tune/configs/*.toml`
  - `benchmarks/espeak_tune/m3_espeak_tuning_benchmark.json`
  - `benchmarks/espeak_tune/m3_espeak_tuning_report.md`
  - `benchmarks/espeak_tune/m3_espeak_tuning_meta.json`

## M3 Kapanis Akisi
- `cli.finish-m3` -> `pipeline.m3_closure.run_m3_closure_workflow`
- Zincir:
  - M3 input hazirlama (`prepare_m3_tts_input`)
  - opsiyonel `tune-m3-espeak` otomasyonu
  - secilen profil ile strict TTS QA gate acik final `run-m3`
- Cikti:
  - `benchmarks/m3_closure_report.json`

## M3 UI Demo Akisi
- `cli.ui-demo` -> `ui_demo.run_ui_demo_server`
- Lokal HTTP panel, backend fonksiyonlarini dogrudan cagirir:
  - `pipeline.m1.run_m1_pipeline` (YouTube URL akisinda)
  - `pipeline.m2_prep.prepare_m2_translation_input` (YouTube URL akisinda)
  - `pipeline.m2.run_m2_pipeline` (YouTube URL akisinda)
  - `pipeline.m3_prep.prepare_m3_tts_input` (opsiyonel)
  - `pipeline.m3.run_m3_pipeline`
- Cikti: JSON sonucunda M3 artefakt yollari + QA ozeti + segment preview
- HTTP endpointler:
  - `POST /run-youtube-dub`: URL tabanli M1->M2->(opsiyonel)M3 zinciri
  - `POST /run-m3`: mevcut run-root uzerinden M3 testi
- UI/JSON cevaplarinda `Cache-Control: no-store` kullanilir (tarayici cache kaynakli eski UI gorunumlerini engellemek icin).

## Windows Startup Akisi
- `open_project.bat`
- Sirali akil:
  - Python bulunurlugu kontrolu
  - `.venv` olusturma (yoksa)
  - `pip install -e .[dev,m2]` (opsiyonel skip)
  - `video-translate doctor` (profil varsa profil ile)
  - `video-translate ui-demo` (opsiyonel no-ui)

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

