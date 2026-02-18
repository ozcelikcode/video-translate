# video-translate

Local and API-free EN-to-TR dubbing pipeline.

Current stage: `M3` complete (YouTube ingest + ASR + EN->TR translate + local TTS dubbing + QA).

## Requirements

- Python 3.12+
- `yt-dlp` available on `PATH`
- `ffmpeg` available on `PATH`

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Run environment doctor:

```bash
video-translate doctor
```

Recommended profile for GTX 1650 (4GB VRAM) + 16GB RAM:

```bash
video-translate doctor --config configs/profiles/gtx1650_i5_12500h.toml
video-translate run-dub --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_i5_12500h.toml
```

One-command flow with strict M3 closure (optional auto-tune + strict QA gate):

```bash
video-translate run-dub --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_espeak.toml --m3-closure
```

Run M1:

```bash
video-translate run-m1 --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

Outputs are written under `runs/<run_id>/`.
Each run also includes `run_manifest.json` for traceability.
M1 also writes `output/qa/m1_qa_report.json` with automatic transcript quality metrics.

Prepare M2 translation input contract from an M1 run:

```bash
video-translate prepare-m2 --run-root runs/m1_YYYYMMDD_HHMMSS
```

Run M2 translation:

```bash
video-translate run-m2 --run-root runs/m1_YYYYMMDD_HHMMSS
```

Prepare M3 TTS input:

```bash
video-translate prepare-m3 --run-root runs/m1_YYYYMMDD_HHMMSS
```

Run M3 local TTS:

```bash
video-translate run-m3 --run-root runs/m1_YYYYMMDD_HHMMSS
```

Lock recommended M3 profile from benchmark:

```bash
video-translate finalize-m3-profile --run-root runs/m1_YYYYMMDD_HHMMSS
```

Run automated espeak tuning (candidate generation + benchmark + report + lock):

```bash
video-translate tune-m3-espeak --run-root runs/m1_YYYYMMDD_HHMMSS
```

Run M3 finish workflow (prepare + optional auto tune + strict QA gate final run):

```bash
video-translate finish-m3 --run-root runs/m1_YYYYMMDD_HHMMSS
```

Run lightweight local M3 UI demo:

```bash
video-translate ui-demo --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765` in browser.
UI now supports YouTube URL based end-to-end flow:
- `M1 -> prepare-m2 -> run-m2 -> (optional) prepare-m3 -> run-m3`
- and existing M3-only run-root testing.

One-click Windows startup (`.bat`):

```bat
open_project.bat
```

Optional:

```bat
open_project.bat 127.0.0.1 8765 --skip-install
open_project.bat 127.0.0.1 8765 --no-ui
```

This script does:
- Python version check (3.12+)
- `.venv` creation (if missing)
- dependency install (`pip install -e .[dev,m2]`)
- `doctor` check
- starts local UI demo

Run M3 with local `espeak` Turkish voice:

```bash
video-translate doctor --config configs/profiles/gtx1650_espeak.toml
video-translate run-m3 --run-root runs/m1_YYYYMMDD_HHMMSS --config configs/profiles/gtx1650_espeak.toml
```

Benchmark M2 profiles on the same input:

```bash
video-translate benchmark-m2 --run-root runs/m1_YYYYMMDD_HHMMSS
```

M2 outputs:
- `output/translate/translation_output.en-tr.json`
- `output/qa/m2_qa_report.json`
- `run_m2_manifest.json` (speed + timing stats)
- `benchmarks/m2_profile_benchmark.json` (multi-profile comparison)

M3 outputs:
- `output/tts/tts_input.tr.json`
- `output/tts/tts_output.tr.json`
- `output/tts/segments/seg_XXXXXX.wav`
- `output/qa/m3_qa_report.json`
- `run_m3_manifest.json`
- `output/tts/tts_preview_stitched.tr.wav`

M3 supports these local backends:
- `mock` (pipeline validation)
- `espeak` (real local synthesis, no API)

For real local model translation, set `translate.backend = "transformers"` in config
and install optional deps:

```bash
pip install -e .[m2]
```

M2 supports optional glossary enforcement via `translate.glossary_path`
and reports terminology + punctuation metrics in `m2_qa_report.json`.
M2 also includes long-segment fluency checks (missing terminal punctuation,
excessive pause punctuation) for dubbing readability.
M2 also reuses repeated source segments to reduce translation time.
For strict production runs, enable QA gate in config:
`translate.qa_fail_on_flags = true` (optionally whitelist by `translate.qa_allowed_flags`).

ASR has automatic OOM fallback. If GPU memory is insufficient, the pipeline
retries on CPU using fallback ASR settings from config.

Fast profile for GTX 1650:

```bash
video-translate run-m1 --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_fast.toml
video-translate run-m2 --run-root runs/m1_YYYYMMDD_HHMMSS --config configs/profiles/gtx1650_fast.toml
```

Strict quality gate profile for GTX 1650:

```bash
video-translate run-m2 --run-root runs/m1_YYYYMMDD_HHMMSS --config configs/profiles/gtx1650_strict.toml
```

## Optional Flags

```bash
video-translate run-m1 \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --config configs/default.toml \
  --run-id demo_run_001 \
  --workspace runs
```

## Notes

- No lip reading is used.
- No paid API is used.
