# Tech Context

## Dil ve Araclar
- `Python 3.12+`
- `ffmpeg` (medya isleme)
- `yt-dlp` (YouTube indirme)
- `faster-whisper` veya esdeger acik ASR
- Yerel acik kaynak EN->TR ceviri modeli
- Yerel acik kaynak Turkce TTS modeli

## Gelistirme Araclari
- `pip` tabanli baslangic kurulum tanimlandi (`pip install -e .[dev]`)
- `ruff` (lint + format)
- `mypy` (tip kontrolu)
- `pytest` (test)

## Teknik KisItlar
- Ucretli API yok
- Zorunlu bulut bagimliligi yok
- Donanim degiskenligi dusunulerek CPU/GPU uyumlu akis hedefi
- Uzun videolarda parca parca isleme desteklenmeli

## Konfigurasyon Ilkesi
- Calisma parametreleri kod icine gomulmeyecek.
- Ortam ve pipeline ayarlari tek konfigurasyon dosyasi uzerinden yonetilecek.
- Varsayilan ayarlar guvenli ve kalite odakli olacak.

## Cikti Standartlari
- Deterministik dosya klasor yapisi
- Ara ciktilarin acik adlandirilmasi
- Final artefaktlarin versiyonlanabilir olmasi

## Mevcut Uygulama Notlari
- CLI: `Typer`
- Konfigurasyon: `TOML` (`configs/default.toml`)
- ASR: `faster-whisper` (yerel model)
- Ingest: harici komutlar (`yt-dlp`, `ffmpeg`)
- On kontrol: `doctor` komutu ile yerel bagimlilik denetimi
- M2 hazirlik: `prepare-m2` ile ceviri giris sozlesmesi uretimi
