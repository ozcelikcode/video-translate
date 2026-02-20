# UI (M3 + YouTube)

Lokal UI arayuzu, mevcut backend akisini kullanir:

- YouTube URL ile `M1 -> prepare-m2 -> run-m2 -> prepare-m3 -> run-m3 -> final MP4`
- Hazir run-root uzerinden `prepare-m3` (opsiyonel) + `run-m3`

## Calistirma

```bash
video-translate ui --host 127.0.0.1 --port 8765
```

Tarayicida ac:

```text
http://127.0.0.1:8765
```

UI uzerinde `UI Build: 2026-02-20-final-mp4-downloads` gorunmelidir.
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
- YouTube akisi sonunda final video:
  - `downloads/<run_id>/video_dubbed.tr.mp4`
- UI, varsayilan olarak ara dosyalari temizler ve yalniz final MP4 teslim eder.
- Bu ortamda `espeak` PATH'te degilse, `espeak` profili ile calisma preflight'ta durur.
- `mock` TTS backend ile is akisi dogrulanabilir.
