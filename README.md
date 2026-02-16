# video-translate

Local and API-free EN-to-TR dubbing pipeline.

Current stage: `M1` (YouTube ingest + audio normalization + timestamped ASR).

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
video-translate run-m1 --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_i5_12500h.toml
video-translate prepare-m2 --run-root runs/m1_YYYYMMDD_HHMMSS
video-translate run-m2 --run-root runs/m1_YYYYMMDD_HHMMSS --config configs/profiles/gtx1650_i5_12500h.toml
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

Benchmark M2 profiles on the same input:

```bash
video-translate benchmark-m2 --run-root runs/m1_YYYYMMDD_HHMMSS
```

M2 outputs:
- `output/translate/translation_output.en-tr.json`
- `output/qa/m2_qa_report.json`
- `run_m2_manifest.json` (speed + timing stats)
- `benchmarks/m2_profile_benchmark.json` (multi-profile comparison)

For real local model translation, set `translate.backend = "transformers"` in config
and install optional deps:

```bash
pip install -e .[m2]
```

M2 supports optional glossary enforcement via `translate.glossary_path`
and reports terminology + punctuation metrics in `m2_qa_report.json`.
M2 also reuses repeated source segments to reduce translation time.

ASR has automatic OOM fallback. If GPU memory is insufficient, the pipeline
retries on CPU using fallback ASR settings from config.

Fast profile for GTX 1650:

```bash
video-translate run-m1 --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_fast.toml
video-translate run-m2 --run-root runs/m1_YYYYMMDD_HHMMSS --config configs/profiles/gtx1650_fast.toml
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
- Sync-sensitive steps (translation, TTS, advanced alignment) are planned for later milestones.
