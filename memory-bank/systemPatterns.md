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

## M2 Hazirlik Akisi
- `cli.prepare-m2` -> `pipeline.m2_prep.prepare_m2_translation_input`
- M1 transcript JSON'undan ceviri giris sozlesmesi uretimi
- Cikti: `output/translate/translation_input.en-tr.json`

## M2 Uygulanan Akis
- `cli.run-m2` -> `pipeline.m2.run_m2_pipeline`
- Ceviri backend secimi: `translate.backends.build_translation_backend`
- Desteklenen backendler: `mock`, `transformers`
- Cikti: `output/translate/translation_output.en-tr.json`
- QA: `qa.m2_report.build_m2_qa_report`
- QA cikti: `output/qa/m2_qa_report.json`

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
