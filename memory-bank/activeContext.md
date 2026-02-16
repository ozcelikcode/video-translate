# Active Context

## Mevcut Odak
Hiz/kalite karsilastirma otomasyonu eklendi. Simdi odak gercek video uzerinde profil secimini netlestirmek.

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
- ASR GPU OOM fallback mekanizmasi eklendi (CPU'ya otomatik gecis).
- GTX1650 + i5-12500H icin profil config eklendi (`configs/profiles/gtx1650_i5_12500h.toml`).
- Doctor M2 bagimlilik kontrolu eklendi (`transformers/sentencepiece/torch`).
- GTX1650 profil bagimliliklari kuruldu ve doctor dogrulamasi basarili.
- M2 hizlandirma: tekrar eden kaynak segmentleri tek sefer cevirme (dedup reuse).
- M2 calisma manifesti eklendi (`run_m2_manifest.json`) - hiz ve sure metrikleri.
- GTX1650 icin hiz odakli ikinci profil eklendi (`configs/profiles/gtx1650_fast.toml`).
- `benchmark-m2` komutu eklendi (profil bazli karsilastirma).
- Benchmark raporu eklendi (`benchmarks/m2_profile_benchmark.json`).
- M2 transformers modeli `facebook/m2m100_418M` olarak guncellendi.
- M1 dokumani eklendi (`docs/milestones/m1.md`).
- M2 dokumani baslatildi (`docs/milestones/m2.md`).
- Temel birim testleri genisletildi ve gecti.

## Aktif Kararlar
- Gelistirme `M1 -> M5` kademeleriyle ilerleyecek.
- Ilk uygulama hedefi `M1` (ingest + ASR + zaman damgalari).
- Proje boyunca gereksiz dosya ve debug artigi birakilmayacak.
- Kod ve klasor adlandirmalari profesyonel ve tutarli olacak.

## Sonraki Adimlar
- M1'i gercek bir YouTube URL ile calistirmak.
- Ornek transcript kalitesini inceleyip M2 ceviri katmani icin segment stratejisini netlestirmek.
- M2 `transformers` backend ile kalite tune etmek (model, batch, token ayarlari).
- M2 kaliteyi gercek veriyle olcup sozluk icerigini alan bazli iyilestirmek.
- M2 `run_m2_manifest.json` metrikleriyle profil bazli hiz karsilastirmasi yapmak.

## Dikkat Notlari
- Senkron hedefi yuksek, fakat lip reading kullanilmayacak.
- Kaliteyi guvencelemek icin metrik odakli QA en bastan planlanacak.
