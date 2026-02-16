# Progress

## Mevcut Durum
Proje M1 uygulama asamasini buyuk oranda tamamladi ve M2 ilk calisir ceviri akisina gecti.

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
- ASR GPU OOM fallback eklendi (otomatik CPU gecisi).
- GTX1650 + i5-12500H profil config eklendi (`configs/profiles/gtx1650_i5_12500h.toml`).
- Doctor kapsami M2 bagimliliklarini da kontrol edecek sekilde genisletildi.
- GTX1650 profili icin `transformers/sentencepiece/torch` kurulumu yapildi ve doctor gecildi.
- M2 hizlandirma eklendi: tekrar eden source segmentler dedup + reuse.
- M2 calisma manifesti eklendi (`run_m2_manifest.json`) - timing/speed metrikleri.
- GTX1650 hiz profili eklendi (`configs/profiles/gtx1650_fast.toml`).
- M2 benchmark komutu eklendi (`benchmark-m2`).
- M2 benchmark raporu eklendi (`benchmarks/m2_profile_benchmark.json`).
- M2 transformer backend `facebook/m2m100_418M` modeline guncellendi.
- M1 milestone dokumani olusturuldu.
- M2 milestone dokumani baslatildi.
- Temel birim testleri genisletildi ve gecti.

## Devam Edenler
- M1 icin gercek video uzerinde entegrasyon calistirmasi henuz yapilmadi.
- ASR kalitesi icin `small/medium` profil tune karsilastirmasi henuz yapilmadi.
- M2 `transformers` backend gercek model kalitesi tune edilmedi.
- M2 glossary kapsaminda alan-ozel terimler henuz zenginlestirilmedi.

## Siradaki Somut Is
- M1'i ornek bir YouTube videosu ile uc uca calistirmak.
- Uretilen transcript kalitesini manuel kontrol etmek.
- M2 yerel EN->TR modeli ile ceviri cikti uretmek.
- M2 kalite kontrollerini eklemek.

## Tamamlama Tahmini (2026-02-16)
- Genel tamamlanma: `%48` (tahmini)
- `M1`: `%90` (donanim fallback dahil, gercek video entegrasyon calistirmasi eksik)
- `M2`: `%68` (benchmark otomasyonu dahil, gercek kalite tuning ve saha dogrulamasi eksik)
- `M3`: `%0`
- `M4`: `%0`
- `M5`: `%0`

## Bilinen Riskler
- Turkce TTS kalite farklari model secimine gore degisebilir.
- Uzun videolarda performans yonetimi icin segment stratejisi kritik.
- Tam profesyonel senkron icin QA metrikleri erken asamada zorunlu.
- Yerel ortamda `yt-dlp` veya `ffmpeg` eksikse pipeline calismaz.
- ASR model secimi (hiz/dogruluk) cihaza gore farkli davranabilir.

