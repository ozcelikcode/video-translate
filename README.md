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
