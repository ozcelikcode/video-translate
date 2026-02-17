# Active Context

## Mevcut Odak
M3 gercek yerel TTS backend'e gecis baslatildi (`espeak`). Simdi odak sure uyumu ve ritim adaptasyonunu iyilestirmek.

## Handoff Snapshot (2026-02-17)
- Son test durumu: `python -m pytest -q` -> `47 passed`.
- CLI komutlari:
  - `doctor`
  - `run-m1`
  - `prepare-m2`
  - `run-m2`
  - `benchmark-m2`
  - `prepare-m3`
  - `run-m3`
- M3 su an `mock` ve `espeak` backendleri ile calisiyor.
- Calisma agaci temiz degil (commit edilmemis degisiklikler var).
- Eklenen yeni M3 dosyalari:
  - `src/video_translate/pipeline/m3.py`
  - `src/video_translate/pipeline/m3_prep.py`
  - `src/video_translate/qa/m3_report.py`
  - `src/video_translate/tts/contracts.py`
  - `src/video_translate/tts/backends.py`
  - `src/video_translate/tts/__init__.py`
  - `tests/test_m3_pipeline.py`
  - `tests/test_m3_prep.py`
  - `tests/test_m3_qa_report.py`
  - `docs/milestones/m3.md`
  - `configs/profiles/gtx1650_espeak.toml`

## Son Degisiklikler
- M1 kod tabani olusturuldu (`src/video_translate`).
- `run-m1` CLI komutu eklendi.
- `doctor` CLI komutu eklendi (ortam on kontrolu).
- Ingest modulleri eklendi (`yt-dlp` indirme, `ffmpeg` normalize).
- ASR modulu eklendi (`faster-whisper`, zaman damgali transcript).
- JSON ve SRT transcript ciktilari eklendi.
- Run izlenebilirligi icin `run_manifest.json` eklendi.
- Konfigurasyon deger dogrulamasi eklendi (gecersiz degerlerde erken hata).
- M1 otomatik kalite raporu eklendi (`output/qa/m1_qa_report.json`).
- `prepare-m2` komutu eklendi.
- M2 ceviri giris sozlesmesi eklendi (`output/translate/translation_input.en-tr.json`).
- `run-m2` komutu eklendi.
- M2 ceviri cikti sozlesmesi eklendi (`output/translate/translation_output.en-tr.json`).
- M2 QA raporu eklendi (`output/qa/m2_qa_report.json`).
- Ceviri backend katmani eklendi (`mock`, `transformers`).
- `run-m2` komutu ile smoke test calistirildi (mock backend).
- M2 terminoloji sozlugu destegi eklendi (`configs/glossary.en-tr.json`).
- M2 ceviri sonrasi glossary postprocess eklendi.
- M2 QA'ya terminal noktalama kontrolu eklendi.
- M2 QA'ya glossary eslesme/kacirma metrikleri eklendi.
- M2 QA'ya uzun segment akicilik kontrolleri eklendi:
  - terminal noktalama eksigi
  - asiri duraklama noktalama yogunlugu (`,`, `;`, `:`)
- M2 QA uzun-segment esikleri konfigurasyona tasindi:
  - `translate.qa_check_long_segment_fluency`
  - `translate.qa_long_segment_word_threshold`
  - `translate.qa_long_segment_max_pause_punct`
- M2 QA kabul kapisi eklendi:
  - `translate.qa_fail_on_flags` ile kalite bayragi varsa kosuyu fail etme
  - `translate.qa_allowed_flags` ile izinli kalite bayragi whitelist'i
- M2 run manifest'e `qa_gate` sonucu eklendi (`enabled/passed/blocked_flags`).
- ASR GPU OOM fallback mekanizmasi eklendi (CPU'ya otomatik gecis).
- GTX1650 + i5-12500H icin profil config eklendi (`configs/profiles/gtx1650_i5_12500h.toml`).
- Doctor M2 bagimlilik kontrolu eklendi (`transformers/sentencepiece/torch`).
- GTX1650 profil bagimliliklari kuruldu ve doctor dogrulamasi basarili.
- M2 hizlandirma: tekrar eden kaynak segmentleri tek sefer cevirme (dedup reuse).
- M2 calisma manifesti eklendi (`run_m2_manifest.json`) - hiz ve sure metrikleri.
- GTX1650 icin hiz odakli ikinci profil eklendi (`configs/profiles/gtx1650_fast.toml`).
- GTX1650 icin strict kalite profili eklendi (`configs/profiles/gtx1650_strict.toml`).
- GTX1650 icin `espeak` TTS profili eklendi (`configs/profiles/gtx1650_espeak.toml`).
- `benchmark-m2` komutu eklendi (profil bazli karsilastirma).
- Benchmark raporu eklendi (`benchmarks/m2_profile_benchmark.json`).
- M2 transformers modeli `facebook/m2m100_418M` olarak guncellendi.
- `prepare-m3` komutu eklendi (M2 translation output -> M3 TTS input).
- `run-m3` komutu eklendi (segment bazli TTS uretimi + M3 QA).
- M3 TTS contract katmani eklendi (`tts_input` / `tts_output`).
- M3 mock TTS backend eklendi (yerel sine-wave uretimi, pipeline dogrulama amacli).
- M3 QA raporu eklendi (`output/qa/m3_qa_report.json`).
- M3 QA gate eklendi (`tts.qa_fail_on_flags`, `tts.qa_allowed_flags`).
- M3 run manifest eklendi (`run_m3_manifest.json`).
- TTS konfigurasyon blogu eklendi (`[tts]`).
- M3 milestone dokumani olusturuldu (`docs/milestones/m3.md`).
- M3'e gercek yerel `espeak` backend eklendi (`tts.backend = espeak`).
- TTS config genisletildi:
  - `tts.espeak_bin`
  - `tts.espeak_voice`
  - `tts.espeak_speed_wpm`
  - `tts.espeak_pitch`
- Doctor/preflight TTS backend kontrolu genisletildi (`espeak` binary denetimi).
- GTX1650 icin `espeak` profili eklendi (`configs/profiles/gtx1650_espeak.toml`).
- TTS backend unit testleri eklendi (`tests/test_tts_backends.py`).
- M1 dokumani eklendi (`docs/milestones/m1.md`).
- M2 dokumani tamamlandi (`docs/milestones/m2.md`).
- Temel birim testleri genisletildi ve gecti.
- M1 gercek URL kosulari tamamlandi:
  - `runs/finalize_m1m2/m1_real_small_cpu`
  - `runs/finalize_m1m2/m1_real_medium_cpu`
- M2 gercek kosu `quality_flags: []` ile tamamlandi.
- M2 benchmark sonucu `gtx1650_fast` profilini onerdi.
- `translate.backends` mojibake onarimi guclendirildi ve testlerle dogrulandi.
- M3 pipeline'a stitched preview artefakti eklendi:
  - `output/tts/tts_preview_stitched.<lang>.wav`
  - `run_m3_manifest.json` -> `outputs.stitched_preview_wav`
- `run-m3` CLI cikti mesajina stitched preview yolu eklendi.
- M3 mock backend ile gercek run dogrulandi (`runs/finalize_m1m2/m1_real_medium_cpu`).
- Not: Bu ortamda `espeak` PATH'te olmadigi icin `run-m3 --config configs/profiles/gtx1650_espeak.toml` preflight'ta duruyor.
- M3 `espeak` backend'e adaptif speaking-rate mekanizmasi eklendi:
  - hedef sureye gore hiz guncelleme (bounded retry)
  - yeni config alanlari: `espeak_adaptive_rate_*`
- GTX1650 profilleri ve varsayilan config bu yeni TTS alanlariyla guncellendi.

## Aktif Kararlar
- Gelistirme `M1 -> M5` kademeleriyle ilerleyecek.
- Ilk uygulama hedefi `M1` (ingest + ASR + zaman damgalari).
- Proje boyunca gereksiz dosya ve debug artigi birakilmayacak.
- Kod ve klasor adlandirmalari profesyonel ve tutarli olacak.

## Sonraki Adimlar
- M3 segment sure uyumunu gelistirmek (konusma hizi/pause adaptasyonu).
- M3 `espeak` ses/rate/pitch parametrelerini gercek veriyle tune etmek.
- M3 `espeak` backend icin kabul esiklerini (`max_duration_delta_seconds`) profil bazli netlestirmek.

## Sonraki Model Icin Net Baslangic Akisi
1. `git status --short` ile degisiklikleri gor.
2. `python -m pytest -q` ile tabani dogrula.
3. `video-translate prepare-m3 --run-root <run_root>` calistir.
4. `video-translate run-m3 --run-root <run_root> --config configs/profiles/gtx1650_espeak.toml` calistir.
5. `output/qa/m3_qa_report.json` ve `run_m3_manifest.json` uzerinden sure delta dagilimini incele.
6. `espeak` voice/rate/pitch ayarlarini kalite hedeflerine gore tune et.

## Dikkat Notlari
- Senkron hedefi yuksek, fakat lip reading kullanilmayacak.
- Kaliteyi guvencelemek icin metrik odakli QA en bastan planlanacak.
