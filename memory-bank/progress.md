# Progress

## Mevcut Durum
Proje M1 uygulama asamasina gecti. Ilk calisabilir pipeline kodu olusturuldu.

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
- M1 milestone dokumani olusturuldu.
- Temel birim testleri genisletildi ve gecti.

## Devam Edenler
- M1 icin gercek video uzerinde entegrasyon calistirmasi henuz yapilmadi.
- Model kalitesi/performans dengesi icin ASR ayarlari tune edilmedi.

## Siradaki Somut Is
- M1'i ornek bir YouTube videosu ile uc uca calistirmak.
- Uretilen transcript kalitesini manuel kontrol etmek.
- M2 icin ceviri katmani arabirimini tanimlamak.

## Bilinen Riskler
- Turkce TTS kalite farklari model secimine gore degisebilir.
- Uzun videolarda performans yonetimi icin segment stratejisi kritik.
- Tam profesyonel senkron icin QA metrikleri erken asamada zorunlu.
- Yerel ortamda `yt-dlp` veya `ffmpeg` eksikse pipeline calismaz.
- ASR model secimi (hiz/dogruluk) cihaza gore farkli davranabilir.
