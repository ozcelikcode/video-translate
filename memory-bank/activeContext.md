# Active Context

## Mevcut Odak
M1 iskeleti saglamlastirildi. Simdi odak M1'i ornek bir video ile calistirip ingest ve ASR ciktilarini dogrulamak.

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
- M1 dokumani eklendi (`docs/milestones/m1.md`).
- Temel birim testleri genisletildi ve gecti.

## Aktif Kararlar
- Gelistirme `M1 -> M5` kademeleriyle ilerleyecek.
- Ilk uygulama hedefi `M1` (ingest + ASR + zaman damgalari).
- Proje boyunca gereksiz dosya ve debug artigi birakilmayacak.
- Kod ve klasor adlandirmalari profesyonel ve tutarli olacak.

## Sonraki Adimlar
- M1'i gercek bir YouTube URL ile calistirmak.
- Ornek transcript kalitesini inceleyip M2 ceviri katmani icin segment stratejisini netlestirmek.
- M2 ceviri katmani arabirimini (girdi/cikti sozlesmesi) tasarlamak.

## Dikkat Notlari
- Senkron hedefi yuksek, fakat lip reading kullanilmayacak.
- Kaliteyi guvencelemek icin metrik odakli QA en bastan planlanacak.
