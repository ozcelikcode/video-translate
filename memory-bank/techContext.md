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
- M2 opsiyonel bagimliliklari: `pip install -e .[m2]`
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
- M2 calistirma: `run-m2` ile ceviri cikti + QA uretimi
- M2 benchmark: `benchmark-m2` ile profil karsilastirma
- M2 glossary: `configs/glossary.en-tr.json` (kaynak terim -> hedef terim)
- M2 QA: terminal noktalama ve glossary eslesme metrikleri
- Donanim profili: `configs/profiles/gtx1650_i5_12500h.toml`
- Donanim hiz profili: `configs/profiles/gtx1650_fast.toml`
- ASR fallback: GPU OOM algilanirsa CPU (`int8`) fallback
- Doctor kontrolu: `transformers/sentencepiece/torch` bagimliliklarini da denetler
- M2 run manifest: `run_m2_manifest.json` icinde hiz/sure olcumleri
- Benchmark raporu: `benchmarks/m2_profile_benchmark.json`
- M2 varsayilan model: `facebook/m2m100_418M`
