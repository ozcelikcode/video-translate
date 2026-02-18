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
- M3 lokal UI demo komutu eklendi (`ui-demo`).
- M3 UI demo backend akisi eklendi (`src/video_translate/ui_demo.py`).
- M3 UI demo testi eklendi (`tests/test_ui_demo.py`).
- Windows one-click calistirma scripti eklendi ve stabilize edildi (`open_project.bat`).
- `open_project.bat` icin `--skip-install` + `--no-ui` akis dogrulamasi basarili.
- UI demo icin YouTube URL entegrasyonu eklendi (`POST /run-youtube-dub`).
- UI demo'da URL tabanli M1->M2->(opsiyonel)M3 zinciri aktif.
- UI demo cache sorunu icin no-cache HTTP basliklari eklendi.
- UI icinde build etiketi eklendi (`2026-02-18-youtube-m3fit`).
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
- UI gorunurluk testi eklendi (`tests/test_ui_demo.py::test_html_page_contains_visible_youtube_controls`).
- UI'da kullanim kolayligi icin "CLI Kullanim Komutlari" text paneli eklendi (`run-dub` ve `--m3-closure` ornekleri).
- Uctan uca tek-komut akis eklendi (`run-dub`):
  - `src/video_translate/pipeline/full_run.py`
  - `src/video_translate/cli.py` (`@app.command("run-dub")`)
  - test: `tests/test_full_run_pipeline.py`
- TTS konfigurasyon blogu eklendi (`[tts]`).
- TTS config'e `espeak` alanlari eklendi (`espeak_bin/voice/speed/pitch`).
- Doctor/preflight `espeak` binary kontrolu eklendi.
- GTX1650 `espeak` profili eklendi (`configs/profiles/gtx1650_espeak.toml`).
- M1 milestone dokumani olusturuldu.
- M2 milestone dokumani baslatildi.
- M3 milestone dokumani baslatildi.
- Temel birim testleri genisletildi ve gecti.
- Son test sonucu: `63 passed` (2026-02-18).

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


