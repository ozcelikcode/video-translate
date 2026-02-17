# UI Demo (M3)

Lokal ve hafif bir test arayuzu eklendi. Bu UI, mevcut backend akisini kullanir:

- `prepare-m3` (opsiyonel)
- `run-m3`

## Calistirma

```bash
video-translate ui-demo --host 127.0.0.1 --port 8765
```

Tarayicida ac:

```text
http://127.0.0.1:8765
```

## Notlar

- Varsayilan run root:
  - `runs/finalize_m1m2/m1_real_medium_cpu`
- Varsayilan profil:
  - `configs/profiles/gtx1650_i5_12500h.toml`
- Bu ortamda `espeak` PATH'te degilse, `espeak` profili ile calisma preflight'ta durur.
- UI demo icin `mock` TTS backend ile akis test edilebilir.

