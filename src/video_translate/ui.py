from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from video_translate.config import load_config
from video_translate.models import M1Artifacts
from video_translate.pipeline.m1 import run_m1_pipeline
from video_translate.pipeline.m2 import run_m2_pipeline
from video_translate.pipeline.m2_prep import prepare_m2_translation_input
from video_translate.pipeline.m3 import run_m3_pipeline
from video_translate.pipeline.m3_prep import prepare_m3_tts_input
from video_translate.preflight import preflight_errors, run_preflight

UI_VERSION = "2026-02-19-output-downloads"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class UIM3Request:
    run_root: Path
    config_path: Path | None
    target_lang: str
    prepare_input: bool
    translation_output_json: Path | None
    tts_input_json: Path | None


@dataclass(frozen=True)
class UIYoutubeRequest:
    source_url: str
    config_path: Path | None
    workspace_dir: Path | None
    run_id: str | None
    emit_srt: bool
    target_lang: str
    run_m3: bool


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _to_ui_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def _collect_downloadables(paths: list[Path | None]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for path in paths:
        if path is None:
            continue
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            continue
        normalized = _to_ui_path(resolved)
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return items


def _resolve_download_path(raw_path: str) -> Path:
    candidate = raw_path.strip()
    if not candidate:
        raise ValueError("path is required.")
    requested = Path(candidate)
    resolved = requested.resolve() if requested.is_absolute() else (PROJECT_ROOT / requested).resolve()
    if PROJECT_ROOT != resolved and PROJECT_ROOT not in resolved.parents:
        raise ValueError("path must stay under project root.")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"Download file not found: {resolved}")
    return resolved


def execute_m3_run(request: UIM3Request) -> dict[str, Any]:
    run_root = request.run_root
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found: {run_root}")
    resolved_run_root = run_root.resolve()

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

    artifacts_payload = {
        "tts_input_json": _to_ui_path(artifacts.tts_input_json),
        "tts_output_json": _to_ui_path(artifacts.tts_output_json),
        "qa_report_json": _to_ui_path(artifacts.qa_report_json),
        "run_manifest_json": _to_ui_path(artifacts.run_manifest_json),
        "stitched_preview_wav": _to_ui_path(artifacts.stitched_preview_wav),
    }
    return {
        "ok": True,
        "run_root": _to_ui_path(resolved_run_root),
        "output_dir": _to_ui_path(resolved_run_root / "output"),
        "target_lang": target_lang,
        "artifacts": artifacts_payload,
        "downloadables": _collect_downloadables(
            [
                artifacts.tts_input_json,
                artifacts.tts_output_json,
                artifacts.qa_report_json,
                artifacts.run_manifest_json,
                artifacts.stitched_preview_wav,
            ]
        ),
        "qa": qa_report,
        "segment_preview": preview_segments,
    }


def execute_youtube_dub_run(request: UIYoutubeRequest) -> dict[str, Any]:
    source_url = request.source_url.strip()
    if not source_url:
        raise ValueError("source_url is required.")

    config = load_config(request.config_path)
    target_lang = request.target_lang.strip() or config.translate.target_language
    preflight_report = run_preflight(
        yt_dlp_bin=config.tools.yt_dlp,
        ffmpeg_bin=config.tools.ffmpeg,
        translate_backend=config.translate.backend,
        tts_backend=config.tts.backend,
        espeak_bin=config.tts.espeak_bin,
        check_translate_backend=True,
        check_tts_backend=request.run_m3,
    )
    issues = preflight_errors(preflight_report)
    if issues:
        raise RuntimeError("Preflight failed: " + " | ".join(issues))

    m1_artifacts = run_m1_pipeline(
        source_url=source_url,
        config=config,
        workspace_dir=request.workspace_dir,
        run_id=request.run_id,
        emit_srt=request.emit_srt,
        preflight_report=preflight_report,
    )
    run_root = m1_artifacts.run_root
    m2_input = run_root / "output" / "translate" / f"translation_input.en-{target_lang}.json"
    m2_output = run_root / "output" / "translate" / f"translation_output.en-{target_lang}.json"
    m2_qa = run_root / "output" / "qa" / "m2_qa_report.json"
    m2_manifest = run_root / "run_m2_manifest.json"
    prepare_m2_translation_input(
        transcript_json_path=m1_artifacts.transcript_json,
        output_json_path=m2_input,
        target_language=target_lang,
    )
    m2_artifacts = run_m2_pipeline(
        translation_input_json_path=m2_input,
        output_json_path=m2_output,
        qa_report_json_path=m2_qa,
        run_manifest_json_path=m2_manifest,
        config=config,
        target_language_override=target_lang,
    )

    m2_payload = {
        "translation_input_json": _to_ui_path(m2_artifacts.translation_input_json),
        "translation_output_json": _to_ui_path(m2_artifacts.translation_output_json),
        "qa_report_json": _to_ui_path(m2_artifacts.qa_report_json),
        "run_manifest_json": _to_ui_path(m2_artifacts.run_manifest_json),
    }
    m3_payload: dict[str, Any] | None = None
    m3_downloadables: list[Path | None] = []
    if request.run_m3:
        m3_input = run_root / "output" / "tts" / f"tts_input.{target_lang}.json"
        prepare_m3_tts_input(
            translation_output_json_path=m2_artifacts.translation_output_json,
            output_json_path=m3_input,
            target_language=target_lang,
        )
        m3_output = run_root / "output" / "tts" / f"tts_output.{target_lang}.json"
        m3_qa = run_root / "output" / "qa" / "m3_qa_report.json"
        m3_manifest = run_root / "run_m3_manifest.json"
        m3_artifacts = run_m3_pipeline(
            tts_input_json_path=m3_input,
            output_json_path=m3_output,
            qa_report_json_path=m3_qa,
            run_manifest_json_path=m3_manifest,
            config=config,
        )
        m3_payload = {
            "tts_input_json": _to_ui_path(m3_artifacts.tts_input_json),
            "tts_output_json": _to_ui_path(m3_artifacts.tts_output_json),
            "qa_report_json": _to_ui_path(m3_artifacts.qa_report_json),
            "run_manifest_json": _to_ui_path(m3_artifacts.run_manifest_json),
            "stitched_preview_wav": _to_ui_path(m3_artifacts.stitched_preview_wav),
        }
        m3_downloadables = [
            m3_artifacts.tts_input_json,
            m3_artifacts.tts_output_json,
            m3_artifacts.qa_report_json,
            m3_artifacts.run_manifest_json,
            m3_artifacts.stitched_preview_wav,
        ]

    result: dict[str, Any] = {
        "ok": True,
        "source_url": source_url,
        "run_root": _to_ui_path(run_root),
        "output_dir": _to_ui_path(run_root / "output"),
        "target_lang": target_lang,
        "downloadables": _collect_downloadables(
            [
                m1_artifacts.source_media,
                m1_artifacts.normalized_audio,
                m1_artifacts.transcript_json,
                m1_artifacts.transcript_srt,
                m1_artifacts.qa_report,
                m1_artifacts.run_manifest,
                m2_artifacts.translation_input_json,
                m2_artifacts.translation_output_json,
                m2_artifacts.qa_report_json,
                m2_artifacts.run_manifest_json,
                *m3_downloadables,
            ]
        ),
        "stages": {
            "m1": _m1_payload(m1_artifacts),
            "m2": m2_payload,
            "m3": m3_payload,
        },
    }
    return result


def _m1_payload(artifacts: M1Artifacts) -> dict[str, Any]:
    return {
        "source_media": _to_ui_path(artifacts.source_media),
        "normalized_audio": _to_ui_path(artifacts.normalized_audio),
        "transcript_json": _to_ui_path(artifacts.transcript_json),
        "transcript_srt": _to_ui_path(artifacts.transcript_srt) if artifacts.transcript_srt else None,
        "qa_report_json": _to_ui_path(artifacts.qa_report),
        "run_manifest_json": _to_ui_path(artifacts.run_manifest),
    }


def _html_page() -> str:
    html = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Video Translate Studio</title>
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
    .focus {
      margin-top: 14px;
      border: 2px solid var(--brand);
      border-radius: 12px;
      background: #f3fffd;
      padding: 10px;
    }
    .focus strong {
      font-size: 14px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
    }
    .err { color: var(--warn); }
    .downloads {
      margin: 0;
      padding-left: 18px;
      font-size: 12px;
      line-height: 1.45;
    }
    .downloads li { margin: 2px 0; }
    .downloads a {
      color: var(--brand);
      text-decoration: none;
    }
    .downloads a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>Video Translate Studio</h1>
      <p><strong>UI Build:</strong> __UI_BUILD__</p>
      <p>YouTube linkinden dogrudan EN->TR dublaj uretimi icin ana operasyon ekrani.</p>
      <div class="focus">
        <strong>Ana Is Akisi:</strong> Asagidaki `YouTube URL` alanina linki yapistir ve
        `YouTube'dan Dublaj Baslat` butonuna bas.
      </div>
      <div class="panel">
        <pre>
YouTube Dub Akisi:
1) URL gir
2) M1 + M2 calisir
3) Opsiyonel M3 ile TTS dublaj uretilir
        </pre>
      </div>
      <div class="panel">
        <pre>
CLI Kullanim Komutlari:
video-translate run-dub --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_i5_12500h.toml
video-translate run-dub --url "https://www.youtube.com/watch?v=VIDEO_ID" --config configs/profiles/gtx1650_espeak.toml --m3-closure
        </pre>
      </div>
      <div class="grid">
        <div class="field">
          <label>YouTube URL</label>
          <input id="sourceUrl" type="text" value="https://www.youtube.com/watch?v=jNQXAC9IVRw" />
        </div>
        <div class="field">
          <label>Workspace Dir (opsiyonel)</label>
          <input id="workspaceDir" type="text" value="runs" />
        </div>
        <div class="field">
          <label>Run ID (opsiyonel)</label>
          <input id="runId" type="text" value="" />
        </div>
        <div class="field">
          <label>Target Lang</label>
          <input id="ytTargetLang" type="text" value="tr" />
        </div>
      </div>
      <label class="check"><input id="ytEmitSrt" type="checkbox" checked /> M1 transcript SRT uret</label>
      <label class="check"><input id="ytRunM3" type="checkbox" checked /> M3 (TTS dublaj) calistir</label>
      <div class="actions">
        <button id="youtubeRunBtn">YouTube'dan Dublaj Baslat</button>
      </div>
      <div class="panel"><pre id="ytStatus">Hazir.</pre></div>
      <div class="panel"><pre id="ytOutput"></pre></div>
      <div class="panel"><pre id="ytOutputDir">Cikti klasoru: -</pre></div>
      <div class="panel">
        <label>Indirilebilir Dosyalar</label>
        <ul id="ytDownloads" class="downloads"></ul>
      </div>
      <hr style="border:0;border-top:1px solid var(--line);margin:14px 0;" />
      <p>Gelişmis M3 araci (opsiyonel, mevcut run-root uzerinden):</p>
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
        <button id="runBtn">M3 Aracini Calistir</button>
        <button id="clearBtn" class="secondary">Temizle</button>
      </div>
      <div class="panel"><pre id="status">Hazir.</pre></div>
      <div class="panel"><pre id="output"></pre></div>
      <div class="panel"><pre id="m3OutputDir">Cikti klasoru: -</pre></div>
      <div class="panel">
        <label>Indirilebilir Dosyalar</label>
        <ul id="m3Downloads" class="downloads"></ul>
      </div>
    </div>
  </div>
  <script>
    const statusEl = document.getElementById("status");
    const outputEl = document.getElementById("output");
    const runBtn = document.getElementById("runBtn");
    const ytStatusEl = document.getElementById("ytStatus");
    const ytOutputEl = document.getElementById("ytOutput");
    const ytOutputDirEl = document.getElementById("ytOutputDir");
    const ytDownloadsEl = document.getElementById("ytDownloads");
    const m3OutputDirEl = document.getElementById("m3OutputDir");
    const m3DownloadsEl = document.getElementById("m3Downloads");
    const youtubeRunBtn = document.getElementById("youtubeRunBtn");
    const clearBtn = document.getElementById("clearBtn");
    function renderOutputDir(element, payload) {
      if (payload && payload.output_dir) {
        element.textContent = "Cikti klasoru: " + payload.output_dir;
        return;
      }
      if (payload && payload.run_root) {
        element.textContent = "Cikti klasoru: " + payload.run_root + "/output";
        return;
      }
      element.textContent = "Cikti klasoru: -";
    }
    function clearDownloadList(listEl) {
      listEl.innerHTML = "";
    }
    function renderDownloadList(listEl, files) {
      clearDownloadList(listEl);
      if (!Array.isArray(files) || files.length === 0) {
        const empty = document.createElement("li");
        empty.textContent = "Henuz dosya yok.";
        listEl.appendChild(empty);
        return;
      }
      files.forEach((filePath) => {
        const item = document.createElement("li");
        const link = document.createElement("a");
        link.href = "/download?path=" + encodeURIComponent(filePath);
        link.textContent = filePath;
        link.setAttribute("download", "");
        item.appendChild(link);
        listEl.appendChild(item);
      });
    }
    renderDownloadList(ytDownloadsEl, []);
    renderDownloadList(m3DownloadsEl, []);
    clearBtn.addEventListener("click", () => {
      statusEl.textContent = "Temizlendi.";
      statusEl.classList.remove("err");
      outputEl.textContent = "";
      renderOutputDir(m3OutputDirEl, null);
      renderDownloadList(m3DownloadsEl, []);
      ytStatusEl.textContent = "Temizlendi.";
      ytStatusEl.classList.remove("err");
      ytOutputEl.textContent = "";
      renderOutputDir(ytOutputDirEl, null);
      renderDownloadList(ytDownloadsEl, []);
    });
    youtubeRunBtn.addEventListener("click", async () => {
      const body = new URLSearchParams();
      body.set("source_url", document.getElementById("sourceUrl").value.trim());
      body.set("config_path", document.getElementById("configPath").value.trim());
      body.set("workspace_dir", document.getElementById("workspaceDir").value.trim());
      body.set("run_id", document.getElementById("runId").value.trim());
      body.set("emit_srt", document.getElementById("ytEmitSrt").checked ? "1" : "0");
      body.set("target_lang", document.getElementById("ytTargetLang").value.trim());
      body.set("run_m3", document.getElementById("ytRunM3").checked ? "1" : "0");
      ytStatusEl.textContent = "YouTube akisi calisiyor...";
      ytStatusEl.classList.remove("err");
      ytOutputEl.textContent = "";
      renderOutputDir(ytOutputDirEl, null);
      clearDownloadList(ytDownloadsEl);
      youtubeRunBtn.disabled = true;
      try {
        const res = await fetch("/run-youtube-dub", { method: "POST", body });
        const payload = await res.json();
        if (!res.ok || !payload.ok) {
          throw new Error(payload.error || ("HTTP " + res.status));
        }
        ytStatusEl.textContent = "YouTube akisi basarili.";
        ytOutputEl.textContent = JSON.stringify(payload, null, 2);
        renderOutputDir(ytOutputDirEl, payload);
        renderDownloadList(ytDownloadsEl, payload.downloadables);
        if (payload.run_root) {
          document.getElementById("runRoot").value = payload.run_root;
        }
      } catch (err) {
        ytStatusEl.textContent = "YouTube akisinda hata olustu.";
        ytStatusEl.classList.add("err");
        ytOutputEl.textContent = String(err);
        renderOutputDir(ytOutputDirEl, null);
        renderDownloadList(ytDownloadsEl, []);
      } finally {
        youtubeRunBtn.disabled = false;
      }
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
      renderOutputDir(m3OutputDirEl, null);
      clearDownloadList(m3DownloadsEl);
      runBtn.disabled = true;
      try {
        const res = await fetch("/run-m3", { method: "POST", body });
        const payload = await res.json();
        if (!res.ok || !payload.ok) {
          throw new Error(payload.error || ("HTTP " + res.status));
        }
        statusEl.textContent = "Basarili.";
        outputEl.textContent = JSON.stringify(payload, null, 2);
        renderOutputDir(m3OutputDirEl, payload);
        renderDownloadList(m3DownloadsEl, payload.downloadables);
      } catch (err) {
        statusEl.textContent = "Hata olustu.";
        statusEl.classList.add("err");
        outputEl.textContent = String(err);
        renderOutputDir(m3OutputDirEl, null);
        renderDownloadList(m3DownloadsEl, []);
      } finally {
        runBtn.disabled = false;
      }
    });
  </script>
</body>
</html>"""
    return html.replace("__UI_BUILD__", UI_VERSION)


def _build_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request_url = urlparse(self.path)
            if request_url.path == "/download":
                form = parse_qs(request_url.query)
                try:
                    download_path = _resolve_download_path(_pick(form, "path", ""))
                except Exception as exc:  # noqa: BLE001
                    self._send_json(400, {"ok": False, "error": str(exc)})
                    return
                self._send_file(download_path)
                return
            if request_url.path != "/":
                self._send_json(404, {"ok": False, "error": "Not found"})
                return
            encoded = _html_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/run-m3", "/run-youtube-dub"}:
                self._send_json(404, {"ok": False, "error": "Not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            form = parse_qs(body)
            try:
                if self.path == "/run-m3":
                    request = UIM3Request(
                        run_root=Path(_pick(form, "run_root", "runs/finalize_m1m2/m1_real_medium_cpu")),
                        config_path=_as_opt_path(form, "config_path"),
                        target_lang=_pick(form, "target_lang", "tr"),
                        prepare_input=_pick(form, "prepare_input", "1") == "1",
                        translation_output_json=_as_opt_path(form, "translation_output_json"),
                        tts_input_json=_as_opt_path(form, "tts_input_json"),
                    )
                    result = execute_m3_run(request)
                else:
                    request = UIYoutubeRequest(
                        source_url=_pick(form, "source_url", ""),
                        config_path=_as_opt_path(form, "config_path"),
                        workspace_dir=_as_opt_path(form, "workspace_dir"),
                        run_id=_as_opt_text(form, "run_id"),
                        emit_srt=_pick(form, "emit_srt", "1") == "1",
                        target_lang=_pick(form, "target_lang", "tr"),
                        run_m3=_pick(form, "run_m3", "1") == "1",
                    )
                    result = execute_youtube_dub_run(request)
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
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_file(self, path: Path) -> None:
            safe_filename = path.name.replace('"', "")
            encoded_filename = quote(path.name)
            content_type, _ = mimetypes.guess_type(path.name)
            self.send_response(200)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}",
            )
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(path.stat().st_size))
            self.end_headers()
            with path.open("rb") as file_handle:
                while True:
                    chunk = file_handle.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

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


def _as_opt_text(form: dict[str, list[str]], key: str) -> str | None:
    values = form.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    return value if value else None


def run_ui_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), _build_handler())
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
