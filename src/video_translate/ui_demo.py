from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from video_translate.config import load_config
from video_translate.pipeline.m3 import run_m3_pipeline
from video_translate.pipeline.m3_prep import prepare_m3_tts_input


@dataclass(frozen=True)
class UIDemoRequest:
    run_root: Path
    config_path: Path | None
    target_lang: str
    prepare_input: bool
    translation_output_json: Path | None
    tts_input_json: Path | None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def execute_m3_demo(request: UIDemoRequest) -> dict[str, Any]:
    run_root = request.run_root
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")

    config = load_config(request.config_path)
    target_lang = request.target_lang.strip() or "tr"
    translation_output_json = request.translation_output_json or (
        run_root / "output" / "translate" / f"translation_output.en-{target_lang}.json"
    )
    tts_input_json = request.tts_input_json or (run_root / "output" / "tts" / f"tts_input.{target_lang}.json")

    if request.prepare_input:
        prepare_m3_tts_input(
            translation_output_json_path=translation_output_json,
            output_json_path=tts_input_json,
            target_language=target_lang,
        )

    output_json = run_root / "output" / "tts" / f"tts_output.{target_lang}.json"
    qa_report_json = run_root / "output" / "qa" / "m3_qa_report.json"
    run_manifest_json = run_root / "run_m3_manifest.json"

    artifacts = run_m3_pipeline(
        tts_input_json_path=tts_input_json,
        output_json_path=output_json,
        qa_report_json_path=qa_report_json,
        run_manifest_json_path=run_manifest_json,
        config=config,
    )
    qa_report = _read_json(qa_report_json)
    output_payload = _read_json(output_json)
    segments = output_payload.get("segments", [])
    preview_segments: list[dict[str, Any]] = []
    if isinstance(segments, list):
        for segment in segments[:5]:
            if isinstance(segment, dict):
                preview_segments.append(
                    {
                        "id": segment.get("id"),
                        "target_duration": segment.get("target_duration"),
                        "synthesized_duration": segment.get("synthesized_duration"),
                        "duration_delta": segment.get("duration_delta"),
                        "target_text": segment.get("target_text"),
                    }
                )

    return {
        "ok": True,
        "run_root": str(run_root),
        "target_lang": target_lang,
        "artifacts": {
            "tts_input_json": str(artifacts.tts_input_json),
            "tts_output_json": str(artifacts.tts_output_json),
            "qa_report_json": str(artifacts.qa_report_json),
            "run_manifest_json": str(artifacts.run_manifest_json),
            "stitched_preview_wav": str(artifacts.stitched_preview_wav),
        },
        "qa": qa_report,
        "segment_preview": preview_segments,
    }


def _html_page() -> str:
    return """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Video Translate M3 UI Demo</title>
  <style>
    :root {
      --bg: #f7f4ee;
      --card: #fffdf8;
      --ink: #1f1a15;
      --muted: #64584e;
      --brand: #0f766e;
      --brand-ink: #e9fffb;
      --line: #ddcfc1;
      --warn: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at 90% 0%, #d7f3ef 0%, transparent 35%),
        radial-gradient(circle at 10% 100%, #fbe3c5 0%, transparent 40%),
        var(--bg);
      color: var(--ink);
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 20px 14px 28px;
    }
    .hero {
      border: 1px solid var(--line);
      background: var(--card);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 10px 24px rgba(21, 15, 10, 0.06);
    }
    h1 { margin: 0 0 8px; font-size: 30px; letter-spacing: 0.2px; }
    p { margin: 0; color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 14px;
    }
    @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
    .field {
      display: flex;
      flex-direction: column;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      padding: 10px;
    }
    label { font-size: 13px; color: var(--muted); }
    input[type="text"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font-size: 14px;
      color: var(--ink);
      background: #fffdf8;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
    }
    .actions { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    button {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 600;
      cursor: pointer;
      background: var(--brand);
      color: var(--brand-ink);
    }
    button.secondary {
      background: #1f2937;
      color: #f3f4f6;
    }
    .panel {
      margin-top: 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      padding: 10px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
    }
    .err { color: var(--warn); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>M3 UI Demo</h1>
      <p>Bu panel mevcut backend akisini (prepare-m3 + run-m3) tek yerden test etmek icindir.</p>
      <div class="grid">
        <div class="field">
          <label>Run Root</label>
          <input id="runRoot" type="text" value="runs/finalize_m1m2/m1_real_medium_cpu" />
        </div>
        <div class="field">
          <label>Config Path (opsiyonel)</label>
          <input id="configPath" type="text" value="configs/profiles/gtx1650_i5_12500h.toml" />
        </div>
        <div class="field">
          <label>Target Lang</label>
          <input id="targetLang" type="text" value="tr" />
        </div>
        <div class="field">
          <label>Translation Output JSON (opsiyonel)</label>
          <input id="translationOutputJson" type="text" value="" />
        </div>
        <div class="field">
          <label>TTS Input JSON (opsiyonel)</label>
          <input id="ttsInputJson" type="text" value="" />
        </div>
      </div>
      <label class="check"><input id="prepareInput" type="checkbox" checked /> once prepare-m3 calistir</label>
      <div class="actions">
        <button id="runBtn">M3 Calistir</button>
        <button id="clearBtn" class="secondary">Temizle</button>
      </div>
      <div class="panel"><pre id="status">Hazir.</pre></div>
      <div class="panel"><pre id="output"></pre></div>
    </div>
  </div>
  <script>
    const statusEl = document.getElementById("status");
    const outputEl = document.getElementById("output");
    const runBtn = document.getElementById("runBtn");
    document.getElementById("clearBtn").addEventListener("click", () => {
      statusEl.textContent = "Temizlendi.";
      statusEl.classList.remove("err");
      outputEl.textContent = "";
    });
    runBtn.addEventListener("click", async () => {
      const body = new URLSearchParams();
      body.set("run_root", document.getElementById("runRoot").value.trim());
      body.set("config_path", document.getElementById("configPath").value.trim());
      body.set("target_lang", document.getElementById("targetLang").value.trim());
      body.set("prepare_input", document.getElementById("prepareInput").checked ? "1" : "0");
      body.set("translation_output_json", document.getElementById("translationOutputJson").value.trim());
      body.set("tts_input_json", document.getElementById("ttsInputJson").value.trim());
      statusEl.textContent = "Calisiyor...";
      statusEl.classList.remove("err");
      outputEl.textContent = "";
      runBtn.disabled = true;
      try {
        const res = await fetch("/run-m3", { method: "POST", body });
        const payload = await res.json();
        if (!res.ok || !payload.ok) {
          throw new Error(payload.error || ("HTTP " + res.status));
        }
        statusEl.textContent = "Basarili.";
        outputEl.textContent = JSON.stringify(payload, null, 2);
      } catch (err) {
        statusEl.textContent = "Hata olustu.";
        statusEl.classList.add("err");
        outputEl.textContent = String(err);
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>"""


def _build_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/":
                self._send_json(404, {"ok": False, "error": "Not found"})
                return
            encoded = _html_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/run-m3":
                self._send_json(404, {"ok": False, "error": "Not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            form = parse_qs(body)
            try:
                request = UIDemoRequest(
                    run_root=Path(_pick(form, "run_root", "runs/finalize_m1m2/m1_real_medium_cpu")),
                    config_path=_as_opt_path(form, "config_path"),
                    target_lang=_pick(form, "target_lang", "tr"),
                    prepare_input=_pick(form, "prepare_input", "1") == "1",
                    translation_output_json=_as_opt_path(form, "translation_output_json"),
                    tts_input_json=_as_opt_path(form, "tts_input_json"),
                )
                result = execute_m3_demo(request)
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"ok": False, "error": str(exc)})
                return
            self._send_json(200, result)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _send_json(self, code: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _pick(form: dict[str, list[str]], key: str, default: str) -> str:
    values = form.get(key, [])
    if not values:
        return default
    value = values[0].strip()
    return value or default


def _as_opt_path(form: dict[str, list[str]], key: str) -> Path | None:
    values = form.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    return Path(value) if value else None


def run_ui_demo_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), _build_handler())
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()

