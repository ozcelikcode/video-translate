# UI (M3 + YouTube)

Lokal UI arayuzu, mevcut backend akisini kullanir:

- YouTube URL ile `M1 -> prepare-m2 -> run-m2 -> (opsiyonel) prepare-m3 -> run-m3`
- Hazir run-root uzerinden `prepare-m3` (opsiyonel) + `run-m3`

## Calistirma

```bash
video-translate ui --host 127.0.0.1 --port 8765
```

Tarayicida ac:

```text
http://127.0.0.1:8765
```

UI uzerinde `UI Build: 2026-02-19-output-downloads` gorunmelidir.
Bu metni gormuyorsaniz tarayicida `Ctrl+F5` ile sert yenileme yapin.

## Notlar

- Varsayilan run root:
  - `runs/finalize_m1m2/m1_real_medium_cpu`
- Varsayilan profil:
  - `configs/profiles/gtx1650_i5_12500h.toml`
- YouTube akisi endpointi:
  - `POST /run-youtube-dub`
- M3-only endpoint:
  - `POST /run-m3`
- Dosya indirme endpointi:
  - `GET /download?path=<repo-ici-dosya-yolu>`
- UI, her kosu sonunda `Cikti klasoru` ve `Indirilebilir Dosyalar` paneli gosterir.
- Bu ortamda `espeak` PATH'te degilse, `espeak` profili ile calisma preflight'ta durur.
- `mock` TTS backend ile is akisi dogrulanabilir.
