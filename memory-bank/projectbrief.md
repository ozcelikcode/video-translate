# Project Brief

## Proje Adi
`video-translate` - YouTube Ingilizce konusmalari icin profesyonel Turkce dublaj uretim sistemi.

## Ana Hedef
Kaynak videodaki Ingilizce konusmayi, `agiz okuma (lip reading) kullanmadan`, yuksek dogrulukta Turkceye cevirip dogal ve guclu zaman senkronuyla dublajlamak.

## Temel Gereksinimler
- Tamamen ucretsiz ve acik kaynak araclar kullanilacak.
- Harici ucretli servis ve kapali API kullanilmayacak.
- Sonuc anlasilir, dogal ve profesyonel olmali.
- Senkron basarimi yuksek olmali; baslangic/bitis ve ritim kacmalari minimize edilmeli.
- Gelistirme kademeli yapilmali, tek seferde tum sistemi kurmaya calisilmamali.
- Kod tabani modern, surdurulebilir ve disiplinli olmali.
- Gereksiz dosya, klasor, debug artigi birakilmamali.

## Kapsam
- YouTube video indirme ve ses cikarma
- ASR (Ingilizce konusma metnine donusturme, zaman damgali)
- EN->TR ceviri
- Turkce TTS ile dublaj sesi uretimi
- Zaman hizalama ve miksaj
- Opsiyonel altyazi destegi
- Kalite kontrol ve raporlama

## Kapsam Disi
- Goruntuden dudak okuma veya yuz takibi ile senkron uretimi
- Ucretli bulut altyapisi bagimliligi

## Basari Kriterleri
- Is akisi uctan uca tek komutla calistirilabilir olmali.
- Ceviri anlam dogrulugu ve terminoloji tutarliligi yuksek olmali.
- Dublaj segmentleri kaynak konusma zamanina guvenilir sekilde oturmali.
- Cikti kalite kontrolunden gecmeden final kabul edilmemeli.

## Asamali Yol Haritasi
- `M1`: Indirme + ses cikarma + zaman damgali ASR
- `M2`: Segment bazli EN->TR ceviri + hizalama
- `M3`: Turkce TTS + temel sure esleme
- `M4`: Gelismis senkron + miks + final render
- `M5`: Otomatik kalite metrikleri + sert kabul esikleri
