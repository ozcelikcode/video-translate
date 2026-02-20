# Progress

## Mevcut Durum
Proje v1 (M1->M3) tamamlandi; uctan uca yerel ve API'siz dublaj akislari calisiyor.

## Tamamlananlar
- Memory Bank klasor yapisi olusturuldu.
- Cekirdek vizyon, kapsam ve kalite hedefleri belirlendi.
- Kademeli teslim modeli (`M1 -> M5`) tanimlandi.
- Lip reading olmadan senkron yaklasimi kesinlestirildi.
- Proje iskeleti olusturuldu (`pyproject.toml`, `src/`, `tests/`, `configs/`).
- `run-m1` komutu ile ingest + normalize + ASR akisi eklendi.
- `doctor` komutu ile ortam bagimlilik kontrolu eklendi.
- Transcript ciktilari icin JSON ve SRT uretimi eklendi.
- Her kosu icin `run_manifest.json` uretimi eklendi.
- Konfigurasyon dogrulama eklendi (gecersiz degerlerde erken hata).
- M1 QA raporu eklendi (`output/qa/m1_qa_report.json`).
- M2 hazirlik komutu eklendi (`prepare-m2`).
- M2 ceviri giris sozlesmesi eklendi (`output/translate/translation_input.en-tr.json`).
- M2 calistirma komutu eklendi (`run-m2`).
- M2 ceviri cikti sozlesmesi eklendi (`output/translate/translation_output.en-tr.json`).
- M2 QA raporu eklendi (`output/qa/m2_qa_report.json`).
- Ceviri backend katmani eklendi (`mock`, `transformers`).
- `run-m2` smoke testi basarili calistirildi (mock backend).
- M2 glossary destegi eklendi (`configs/glossary.en-tr.json`).
- M2 ceviri sonrasi glossary postprocess eklendi.
- M2 QA'ya terminal noktalama ve glossary eslesme metrikleri eklendi.
- M2 QA'ya uzun segment akicilik kontrolleri eklendi (terminal eksigi + asiri duraklama noktalama).
- M2 uzun segment QA esikleri konfigurasyona eklendi.
- M2 QA kabul kapisi eklendi (`qa_fail_on_flags`, `qa_allowed_flags`).
- M2 run manifest'e QA gate sonucu eklendi (`qa_gate`).
- ASR GPU OOM fallback eklendi (otomatik CPU gecisi).
- GTX1650 + i5-12500H profil config eklendi (`configs/profiles/gtx1650_i5_12500h.toml`).
- Doctor kapsami M2 bagimliliklarini da kontrol edecek sekilde genisletildi.
- GTX1650 profili icin `transformers/sentencepiece/torch` kurulumu yapildi ve doctor gecildi.
- M2 hizlandirma eklendi: tekrar eden source segmentler dedup + reuse.
- M2 calisma manifesti eklendi (`run_m2_manifest.json`) - timing/speed metrikleri.
- GTX1650 hiz profili eklendi (`configs/profiles/gtx1650_fast.toml`).
- GTX1650 strict kalite profili eklendi (`configs/profiles/gtx1650_strict.toml`).
- M2 benchmark komutu eklendi (`benchmark-m2`).
- M2 benchmark raporu eklendi (`benchmarks/m2_profile_benchmark.json`).
- M2 transformer backend `facebook/m2m100_418M` modeline guncellendi.
- M1 gercek YouTube calismasi tamamlandi (`jNQXAC9IVRw`, small/medium CPU profilleri).
- M2 gercek veri calismasi tamamlandi ve QA temiz gecildi (`quality_flags: []`).
- M2 karakter kodlama onarimi guclendirildi (UTF-8 mojibake repair).
- M2 benchmark sonucu ile onerilen profil netlesti (`gtx1650_fast`).
- M3 hazirlik komutu eklendi (`prepare-m3`).
- M3 calistirma komutu eklendi (`run-m3`).
- M3 TTS contract yapisi eklendi (`tts_input` / `tts_output`).
- M3 mock TTS backend eklendi.
- M3 gercek yerel `espeak` backend eklendi.
- M3 QA raporu eklendi (`output/qa/m3_qa_report.json`).
- M3 QA gate eklendi (`tts.qa_fail_on_flags`, `tts.qa_allowed_flags`).
- M3 run manifest eklendi (`run_m3_manifest.json`).
- M3 stitched preview artefakti eklendi (`output/tts/tts_preview_stitched.<lang>.wav`).
- M3 run manifest `outputs` alanina `stitched_preview_wav` eklendi.
- M3 `espeak` backend'e adaptif speaking-rate mekanizmasi eklendi.
- TTS config'e adaptif hiz alanlari eklendi (`espeak_adaptive_rate_*`).
- M3 benchmark komutu eklendi (`benchmark-m3`).
- M3 benchmark raporu eklendi (`benchmarks/m3_profile_benchmark.json`).
- Benchmark stitched preview dosyalari profil bazli ayrildi (`benchmarks/tts_preview_stitched.<profile>.wav`).
- M3 tuning markdown rapor komutu eklendi (`report-m3-tuning`).
- M3 tuning raporu eklendi (`benchmarks/m3_tuning_report.md`).
- M3 lokal UI komutu eklendi (`ui`).
- M3 UI backend akisi eklendi (`src/video_translate/ui.py`).
- M3 UI testi eklendi (`tests/test_ui.py`).
- Windows one-click calistirma scripti eklendi ve stabilize edildi (`open_project.bat`).
- `open_project.bat` icin `--skip-install` + `--no-ui` akis dogrulamasi basarili.
- UI icin YouTube URL entegrasyonu eklendi (`POST /run-youtube-dub`).
- UI'da URL tabanli M1->M2->(opsiyonel)M3 zinciri aktif.
- UI cache sorunu icin no-cache HTTP basliklari eklendi.
- UI icinde build etiketi eklendi (`2026-02-20-final-mp4-downloads`).
- M3 sure post-fit eklendi: kisa segmentlere sessizlik padding.
- M3 manifest'e `duration_postfit` metrikleri eklendi.
- M3 sure post-fit genisletildi: uzun segmentlere WAV trim eklendi.
- M3 benchmark/tuning raporlarina post-fit metrikleri eklendi (pad/trim segment+sure).
- M3 profil finalizasyon komutu eklendi (`finalize-m3-profile`).
- M3 finalizasyon secim raporu eklendi (`benchmarks/m3_profile_selection.json`).
- M3 QA post-fit guard eklendi (segment/sure oran bayraklari).
- TTS config'e post-fit QA esikleri eklendi (`qa_max_postfit_segment_ratio`, `qa_max_postfit_seconds_ratio`).
- M3 espeak otomatik tuning komutu eklendi (`tune-m3-espeak`).
- M3 espeak tuning zinciri eklendi (aday uretim + benchmark + tuning report + finalize).
- M3 kapanis workflow komutu eklendi (`finish-m3`).
- M3 kapanis raporu eklendi (`benchmarks/m3_closure_report.json`).
- M3 dosya adlandirma standardi duzeltildi:
  - `src/video_translate/pipeline/m3_finish.py` -> `src/video_translate/pipeline/m3_closure.py`
  - `tests/test_m3_finish.py` -> `tests/test_m3_closure.py`
- UI'da YouTube link giris gorunurlugu guclendirildi (odak kutusu + acik yonlendirme metni).
- UI gorunurluk testi eklendi (`tests/test_ui.py::test_html_page_contains_visible_youtube_controls`).
- UI'da kullanim kolayligi icin "CLI Kullanim Komutlari" text paneli eklendi (`run-dub` ve `--m3-closure` ornekleri).
- UI ana ekran dili "demo/test" yerine production operasyon diline guncellendi (`Video Translate Studio`).
- Port cakisma sertlestirmesi eklendi:
  - `open_project.bat` UI acilisindan once ayni porttaki eski LISTENING processleri kapatir.
- `open_project.bat` kapanma hatasi cozuldu:
  - `... was unexpected at this time.` batch parser hatasi giderildi.
  - Port temizleme adimi `for/findstr` yerine guvenli PowerShell tek satirina alindi.
- ASR fallback iyilestirmesi:
  - `cublas64_12.dll` / CUDA runtime DLL eksikligi hatalarinda M1 ASR otomatik CPU fallback yapar.
  - test: `tests/test_asr_fallback.py` guncellendi.
- ASR fallback davranisi guclendirildi:
  - Primary ASR denemesi basarisizsa ve fallback ayarlari farkliysa (tipik `cuda -> cpu`) fallback zorunlu denenir.
  - Generator-iterasyon hatalari da fallback kapsamina alindi (`_transcribe_and_collect`).
  - Tam test sonucu: `70 passed` (2026-02-20).
- Uctan uca tek-komut akis eklendi (`run-dub`):
  - `src/video_translate/pipeline/full_run.py`
  - `src/video_translate/cli.py` (`@app.command("run-dub")`)
  - test: `tests/test_full_run_pipeline.py`
- UI cikti erisimi gelistirildi:
  - guvenli dosya indirme endpointi eklendi (`GET /download?path=...`)
  - UI sonucu icin `Cikti klasoru` ve `Indirilebilir Dosyalar` panelleri eklendi
  - YouTube ve M3 cevap payload'larina `output_dir` + `downloadables` eklendi
  - testler guncellendi (`tests/test_ui.py`)
- UI adlandirma standardi temizlendi:
  - modül: `src/video_translate/ui.py`
  - CLI: `video-translate ui`
  - dokuman: `docs/ui.md`
  - test: `tests/test_ui.py`
  - `open_project.bat` UI baslatma komutu `ui` olarak guncellendi
- Final teslim odakli YouTube UI akisi eklendi:
  - yeni pipeline: `src/video_translate/pipeline/delivery.py`
  - final cikti: `downloads/<run_id>/video_dubbed.tr.mp4`
  - kalite ozeti: `downloads/<run_id>/quality_summary.tr.json`
  - UI indirilebilir dosyalar listesi final MP4 ile sinirlandi
  - ara dosya temizligi varsayilan acik (`cleanup_intermediate=true`)
  - testler: `tests/test_delivery.py`, `tests/test_ui.py`
- UI YouTube asenkron ilerleme yuzdesi eklendi:
  - `POST /run-youtube-dub` job payload dondurur (`job_id`, `status`, `progress_percent`, `phase`)
  - `GET /job-status` polling ile canli durum takibi yapilir
  - UI ilerleme cubugu `%` metni ve faz metni anlik guncellenir
  - test guncellemesi: `tests/test_ui.py` progress assertleri
- Son test sonucu tekrar dogrulandi: `70 passed` (2026-02-20).
- TTS beep/diiit sorunu giderildi:
  - kok neden: kullanim profillerinde `tts.backend=mock` oldugu icin final videoda konusma yerine test tonu uretiliyordu
  - cozum:
    - `configs/profiles/gtx1650_i5_12500h.toml` -> `tts.backend="espeak"`
    - `configs/profiles/gtx1650_fast.toml` -> `tts.backend="espeak"`
    - `configs/profiles/gtx1650_strict.toml` -> `tts.backend="espeak"`
  - final akis guvencesi:
    - `run-dub` ve UI YouTube final akisinda `tts.backend=mock` bloklanir
    - kullaniciya acik hata mesajiyla `espeak` profiline gecis yonlendirmesi verilir
  - testler:
    - `tests/test_full_run_pipeline.py::test_run_full_dub_pipeline_rejects_mock_tts_backend`
    - `tests/test_ui.py::test_execute_youtube_dub_run_rejects_mock_tts_backend`
  - yeni toplam test sonucu: `72 passed` (2026-02-20).
- eSpeak command fallback eklendi:
  - `preflight` icinde `espeak` yoksa `espeak-ng` de otomatik kontrol edilir
  - TTS backend build asamasinda `espeak` <-> `espeak-ng` fallback uygulanir
  - testler:
    - `tests/test_preflight.py::test_run_preflight_espeak_backend_accepts_espeak_ng_fallback`
    - `tests/test_tts_backends.py::test_build_tts_backend_espeak_prefers_espeak_ng_when_espeak_missing`
  - yeni toplam test sonucu: `74 passed` (2026-02-20).
- Adlandirma disiplin karari netlestirildi:
  - uretim tarafinda `demo/test` adlari kullanilmaz
  - test kodlari yalnizca `tests/` altinda tutulur
  - debug artefaktlari ayrik debug alaninda tutulur
- TTS konfigurasyon blogu eklendi (`[tts]`).
- TTS config'e `espeak` alanlari eklendi (`espeak_bin/voice/speed/pitch`).
- Doctor/preflight `espeak` binary kontrolu eklendi.
- GTX1650 `espeak` profili eklendi (`configs/profiles/gtx1650_espeak.toml`).
- M1 milestone dokumani olusturuldu.
- M2 milestone dokumani baslatildi.
- M3 milestone dokumani baslatildi.
- Temel birim testleri genisletildi ve gecti.
- Son test sonucu: `74 passed` (2026-02-20).

## Calisma Agaci Durumu (Handoff)
- Commit edilmemis degisiklikler mevcut.
- Yeni (untracked) dosyalar:
  - `configs/profiles/gtx1650_strict.toml`
  - `docs/milestones/m3.md`
  - `src/video_translate/pipeline/m3.py`
  - `src/video_translate/pipeline/m3_prep.py`
  - `src/video_translate/qa/m3_report.py`
  - `src/video_translate/tts/__init__.py`
  - `src/video_translate/tts/backends.py`
  - `src/video_translate/tts/contracts.py`
  - `tests/test_m3_pipeline.py`
  - `tests/test_m3_prep.py`
  - `tests/test_m3_qa_report.py`
- Ayrica bircok dosyada staged olmayan degisiklik var (CLI, config, M2 QA, docs, memory-bank).

## Devam Edenler
- Bu repo kapsaminda zorunlu gelistirme kalemi kalmadi; yeni iyilestirmeler backlog olarak acilacak.

## Siradaki Somut Is
- Zorunlu bir sonraki adim yok. Yeni is talepleri yeni milestone/backlog olarak planlanacak.

## Tamamlama Tahmini (2026-02-18)
- Genel tamamlanma (v1 kapsam): `%100`
- `M1`: `%100` (gercek URL calismasi + QA raporu tamam)
- `M2`: `%100` (gercek ceviri kosusu + QA + benchmark tamam)
- `M3`: `%100` (closure workflow + otomatik tuning + QA gate + UI + run-dub tek-komut akis + testler tamam)
- `M4`: `%0` (bu surumde backlog)
- `M5`: `%0` (bu surumde backlog)

## M1/M2 Durum Notu
- M1 ve M2 milestone kabul kriterleri karsilandi ve %100 olarak isaretlendi.
- M3 de tamamlandi; sonraki kalite/genisletme isleri backlog olarak acilacak.

## Bilinen Riskler
- Turkce TTS kalite farklari model secimine gore degisebilir.
- Uzun videolarda performans yonetimi icin segment stratejisi kritik.
- Tam profesyonel senkron icin QA metrikleri erken asamada zorunlu.
- Yerel ortamda `yt-dlp` veya `ffmpeg` eksikse pipeline calismaz.
- ASR model secimi (hiz/dogruluk) cihaza gore farkli davranabilir.



