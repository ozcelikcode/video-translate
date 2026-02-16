# Product Context

## Neden Bu Proje?
Ingilizce icerikleri Turkce izlemek isteyen kullanicilar icin, dogal duyulan ve zamanlama acisindan guclu bir dublaj cozumune ihtiyac var. Hedef, altyaziya mecbur kalmadan anlasilir ve akici bir izleme deneyimi saglamak.

## Cozdugu Problemler
- Ingilizce konusmayi Turkce dinleme ihtiyaci
- Otomatik sistemlerdeki robotik ses ve kotu zamanlama sorunu
- Altyaziya bagimli izleme deneyimi
- Ucretli API bagimliligi nedeniyle surdurulebilirlik riski

## Nasil Calismali?
- Video girdisi alinir, ses normalize edilir.
- Konusma zaman damgali olarak yaziya dokulur.
- Metin baglam korunarak EN->TR cevrilir.
- Turkce seslendirme uretilir.
- Ses segmentleri kaynak konusma zamanina gore hizalanir.
- Cikti tek videoda birlestirilir, istege bagli altyazi eklenir.

## Kullanici Deneyimi Hedefleri
- Basit ve guvenilir komut satiri kullanimi
- Tutarli sonuclar
- Hata durumlarinda anlasilir mesajlar
- Profesyonel cikti klasor duzeni
- Uzun videolarda da stabil calisma

## Kalite Ilkeleri
- `Lip reading yok`: senkron yalnizca ses/zaman akisina gore yapilir.
- Ceviri dogrulugu ve anlam korunumu onceliklidir.
- Sesin anlasilirliligi ve dogalligi korunur.
- Kalite esigini karsilamayan ciktilar raporlanir.
