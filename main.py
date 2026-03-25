"""
main.py  –  FastAPI application entry point.

Architecture: Background Job + Polling
  - POST /process      → starts background job, returns job_id instantly
  - GET  /status/{id}  → returns job progress (poll every 3s from frontend)
  - GET  /download/{id}→ returns the finished DOCX file
  - GET  /             → serves the frontend UI

This eliminates SSE stream timeouts entirely. No matter how many files
are uploaded or how long processing takes, the frontend just keeps polling.
"""

import asyncio
import base64
import json
import logging
import re
import os
import uuid
import time
from pathlib import Path
from typing import AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response

from tools import (
    parse_vtt,
    parse_docx,
    chunk_text,
    TEMPLATE_SCHEMA,
    EXTRACTION_SYSTEM,
    SYNTHESIS_SYSTEM,
    merge_chunk_results,
    safe_parse_json,
    _clean_transcript,
)
from docx_builder import build_docx

# ── bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Transcript → Customer Profile", version="3.0.0")


# ── In-memory job store ────────────────────────────────────────────────────────
# Each job entry:
# {
#   "status":   "queued" | "running" | "done" | "error",
#   "step":     str,          # human-readable current step
#   "pct":      int,          # 0-100
#   "error":    str | None,   # error message if status=="error"
#   "filename": str | None,   # output filename when done
#   "docx_b64": str | None,   # base64-encoded DOCX when done
#   "created":  float,        # time.time() — for cleanup
# }
_JOBS: dict[str, dict] = {}

# Clean up jobs older than 1 hour to avoid memory leak
_JOB_TTL = 3600


def _cleanup_old_jobs():
    now = time.time()
    to_delete = [jid for jid, j in _JOBS.items() if now - j["created"] > _JOB_TTL]
    for jid in to_delete:
        del _JOBS[jid]
    if to_delete:
        logger.info("Cleaned up %d expired jobs", len(to_delete))


def _new_job() -> str:
    _cleanup_old_jobs()
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        "status":   "queued",
        "step":     "Queued — waiting to start…",
        "pct":      0,
        "error":    None,
        "filename": None,
        "docx_b64": None,
        "created":  time.time(),
    }
    return job_id


def _update(job_id: str, **kwargs):
    if job_id in _JOBS:
        _JOBS[job_id].update(kwargs)


# ── Content-filter sanitizer ──────────────────────────────────────────────────
_FILTER_RE = re.compile(
    r"\b(sex|sexy|naked|nude|porn|erotic|fetish|orgasm|cock|dick|"
    r"pussy|boob|breast|vagina|penis|anal|lesbian|intercourse)\b",
    re.IGNORECASE,
)

def _sanitize(text: str) -> str:
    return _FILTER_RE.sub("[REDACTED]", text)


# ── NTTHAI Claude client ───────────────────────────────────────────────────────
class NTTHAIClient:
    """
    Async wrapper around the NTTHAI API (OpenAI-compatible).
    Auth: Authorization: Bearer app:<api_id>:<api_secret>
    - Timeout = 300s per call
    - 429 / 5xx → retry up to 4 times with backoff
    - DNS/connect errors → fail immediately
    """

    _TIMEOUT = 300

    def __init__(self, api_id: str, api_secret: str, base_url: str, model: str):
        self.url     = f"{base_url.rstrip('/')}/chat/completions"
        self.model   = model
        self.headers = {
            "Authorization": f"Bearer app:{api_id}:{api_secret}",
            "Content-Type":  "application/json",
        }

    async def chat(self, system: str, user: str, max_tokens: int = 8000) -> str:
        payload = {
            "model":      self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        }

        last_exc: Exception | None = None

        for attempt in range(1, 5):
            try:
                async with httpx.AsyncClient(timeout=self._TIMEOUT) as http:
                    resp = await http.post(self.url, headers=self.headers, json=payload)

                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 15 * attempt))
                    logger.warning("NTTHAI 429 rate-limit (attempt %d/4) — waiting %d s", attempt, wait)
                    await asyncio.sleep(wait)
                    last_exc = Exception(f"NTTHAI 429 (attempt {attempt})")
                    continue

                if resp.status_code in (500, 502, 503, 504):
                    wait = 5 * attempt
                    logger.warning("NTTHAI %d (attempt %d/4) — retrying in %d s", resp.status_code, attempt, wait)
                    await asyncio.sleep(wait)
                    last_exc = Exception(f"NTTHAI {resp.status_code} (attempt {attempt})")
                    continue

                if not resp.is_success:
                    err_body = resp.text[:1000]
                    logger.error("NTTHAI HTTP %d (attempt %d/4): %s", resp.status_code, attempt, err_body)
                    resp.raise_for_status()

                data    = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.warning("NTTHAI returned no choices (attempt %d/4): %s", attempt, str(data)[:300])
                    last_exc = Exception("NTTHAI returned empty choices")
                    await asyncio.sleep(5 * attempt)
                    continue

                text = choices[0].get("message", {}).get("content", "")
                if not text:
                    logger.warning("NTTHAI empty content (attempt %d/4)", attempt)
                    last_exc = Exception("NTTHAI returned empty content")
                    await asyncio.sleep(5 * attempt)
                    continue

                return text

            except httpx.TimeoutException as exc:
                wait = 10 * attempt
                logger.warning("NTTHAI TIMEOUT (attempt %d/4) — retrying in %d s", attempt, wait)
                last_exc = exc
                await asyncio.sleep(wait)

            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                logger.error("NTTHAI unreachable (DNS/connect): %s", exc)
                raise RuntimeError(
                    f"Cannot reach NTTHAI API ({self.url}). "
                    "Check your internet connection."
                ) from exc

            except httpx.RequestError as exc:
                wait = 5 * attempt
                logger.warning("NTTHAI network error (attempt %d/4) %s: %s — retrying in %d s",
                               attempt, type(exc).__name__, exc, wait)
                last_exc = exc
                await asyncio.sleep(wait)

        raise last_exc or Exception("NTTHAI chat failed after 4 attempts")


def get_client() -> NTTHAIClient:
    ntthai_id     = os.getenv("NTTHAI_API_ID", "")
    ntthai_secret = os.getenv("NTTHAI_API_SECRET", "")
    ntthai_url    = os.getenv("NTTHAI_BASE_URL", "https://api.ntthai.ai/v1")
    ntthai_model  = os.getenv("NTTHAI_MODEL", "claude-sonnet-4-5")

    if not ntthai_id or not ntthai_secret:
        raise RuntimeError("NTTHAI Claude not configured. Set NTTHAI_API_ID + NTTHAI_API_SECRET in .env")

    logger.info("LLM: NTTHAI Claude %s (direct httpx)", ntthai_model)
    return NTTHAIClient(ntthai_id, ntthai_secret, ntthai_url, ntthai_model)


# ── File parsing helpers ───────────────────────────────────────────────────────
async def extract_text(filename: str, raw: bytes) -> str:
    fname = filename.lower()
    if fname.endswith(".vtt"):
        return parse_vtt.invoke({"content": raw.decode("utf-8", errors="replace")})
    if fname.endswith(".docx"):
        return parse_docx.invoke({"file_bytes_hex": raw.hex()})
    if fname.endswith((".txt", ".doc", ".md")):
        return _clean_transcript(raw.decode("utf-8", errors="replace"))
    return raw.decode("utf-8", errors="replace")


# ── LLM call helpers ───────────────────────────────────────────────────────────
async def extract_chunk(client: NTTHAIClient, chunk: str, idx: int, total: int) -> dict:
    def _prompt(c: str) -> str:
        return (
            f"This is chunk {idx + 1} of {total} from the uploaded transcript(s).\n"
            f"Extract all relevant information:\n\n{c}"
        )

    async def _call(prompt: str) -> dict:
        text = await client.chat(EXTRACTION_SYSTEM, prompt, max_tokens=4000)
        if not text or not text.strip():
            logger.warning("Chunk %d/%d — LLM returned empty text", idx + 1, total)
            return {}
        result = safe_parse_json(text)
        if not result:
            logger.warning("Chunk %d/%d — JSON parse failed. Preview: %.200s", idx + 1, total, text)
        return result or {}

    try:
        return await _call(_prompt(chunk))

    except RuntimeError:
        raise

    except Exception as exc:
        exc_str = str(exc)

        if "content_filter" in exc_str or "ResponsibleAIPolicyViolation" in exc_str:
            logger.warning("Chunk %d/%d — content_filter. Retrying with sanitized text…", idx + 1, total)
            try:
                result = await _call(_prompt(_sanitize(chunk)))
                if result:
                    logger.info("Chunk %d/%d — sanitized retry succeeded ✓", idx + 1, total)
                return result
            except Exception as retry_exc:
                logger.warning(
                    "Chunk %d/%d — sanitized retry failed: %s — skipping",
                    idx + 1, total, retry_exc,
                )
                return {}

        logger.warning(
            "Chunk %d/%d — %s: %s — skipping",
            idx + 1, total,
            type(exc).__name__,
            exc_str or "(no message)",
        )
        return {}


async def synthesize(client: NTTHAIClient, merged: dict) -> dict:
    merged_json = json.dumps(merged, indent=2)
    if len(merged_json) > 80_000:
        logger.warning("Merged data too large for synthesis (%d chars) — skipping", len(merged_json))
        return merged
    prompt = (
        "Synthesize this merged transcript data into clean professional summaries:\n"
        + merged_json
    )
    text   = await client.chat(SYNTHESIS_SYSTEM, prompt, max_tokens=8000)
    result = safe_parse_json(text)
    return result if result else merged


# ── Core pipeline (runs entirely in background) ────────────────────────────────
async def _run_pipeline(job_id: str, file_data: list[tuple[str, bytes]]):
    """
    Processes all uploaded files in the background.
    Updates _JOBS[job_id] with progress at each step.
    No SSE, no streaming — just async work + job store updates.
    """
    try:
        # Step 1 – init LLM client
        _update(job_id, step="Connecting to LLM…", pct=3, status="running")
        try:
            client = get_client()
        except RuntimeError as e:
            _update(job_id, status="error", error=str(e))
            return

        label = "NTTHAI Claude Sonnet"
        _update(job_id, step=f"LLM ready → {label}", pct=6)

        # Step 2 – parse uploaded files
        _update(job_id, step="Reading uploaded files…", pct=8)
        all_text_parts = []
        for filename, raw in file_data:
            _update(job_id, step=f"Parsing {filename}…", pct=10)
            try:
                text = await extract_text(filename, raw)
                if text.strip():
                    all_text_parts.append(f"=== FILE: {filename} ===\n{text}")
            except Exception as ex:
                logger.warning("Could not parse %s: %s", filename, ex)

        if not all_text_parts:
            _update(job_id, status="error", error="No readable content found in the uploaded files.")
            return

        combined = "\n\n".join(all_text_parts)
        _update(job_id, step=f"Extracted {len(combined) // 1000}k chars from {len(file_data)} file(s)", pct=14)

        # Step 3 – chunk text
        chunk_size  = 24_000
        overlap     = 400
        chunks_json = chunk_text.invoke({"text": combined, "chunk_size": chunk_size, "overlap": overlap})
        chunks: list[str] = json.loads(chunks_json)
        _update(job_id, step=f"Split into {len(chunks)} chunk(s) · processing with {label}…", pct=18)

        # Step 4 – extract per chunk CONCURRENTLY (semaphore = 3 at a time)
        # This is the key fix: instead of sequential processing that times out,
        # we run up to 3 chunks in parallel, cutting total time by ~3x.
        sem = asyncio.Semaphore(3)

        async def _bounded_extract(i: int, chunk: str) -> dict:
            async with sem:
                pct = 20 + int((i / len(chunks)) * 50)
                _update(job_id,
                        step=f"Analyzing chunk {i + 1}/{len(chunks)} with {label}…",
                        pct=pct)
                return await extract_chunk(client, chunk, i, len(chunks))

        chunk_results = await asyncio.gather(
            *[_bounded_extract(i, c) for i, c in enumerate(chunks)]
        )

        # Step 5 – merge
        _update(job_id, step="Merging findings across all chunks…", pct=73)
        merged = merge_chunk_results(list(chunk_results))

        # Step 6 – synthesize (de-duplicate) when more than one chunk
        final_data = merged
        if len(chunks) > 1:
            _update(job_id, step="Synthesizing and de-duplicating…", pct=83)
            try:
                final_data = await synthesize(client, merged)
            except Exception as ex:
                logger.warning("Synthesis failed (%s: %s) — using raw merge", type(ex).__name__, ex)
                final_data = merged

        # Step 7 – build DOCX
        _update(job_id, step="Generating Word document…", pct=93)
        template_path = os.path.join(os.path.dirname(__file__), "word_template.docx")
        docx_bytes    = build_docx(final_data, template_path=template_path)

        b64         = base64.b64encode(docx_bytes).decode()
        client_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", final_data.get("client_name") or "Customer_Profile")
        filename    = f"{client_name}_Discovery_Profile.docx"

        _update(job_id,
                status="done",
                step="Document is ready for download!",
                pct=100,
                filename=filename,
                docx_b64=b64)

        logger.info("Job %s completed → %s", job_id, filename)

    except Exception as exc:
        logger.exception("Unhandled pipeline error in job %s: %s", job_id, exc)
        _update(job_id, status="error", error=str(exc))


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse((Path(__file__).parent / "index.html").read_text(encoding="utf-8"))


@app.post("/process")
async def process(files: list[UploadFile] = File(...)):
    """
    Accepts uploaded files, creates a background job, returns job_id immediately.
    The frontend then polls /status/{job_id} every 3 seconds.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Read all file bytes eagerly — UploadFile objects are not safe to pass
    # into background tasks after the request completes.
    file_data: list[tuple[str, bytes]] = []
    for f in files:
        raw = await f.read()
        file_data.append((f.filename or "unknown", raw))

    job_id = _new_job()
    logger.info("Job %s created for %d file(s)", job_id, len(file_data))

    # Fire and forget — pipeline runs fully in background
    asyncio.ensure_future(_run_pipeline(job_id, file_data))

    return JSONResponse({"job_id": job_id})


@app.get("/status/{job_id}")
async def status(job_id: str):
    """
    Returns current job status. Frontend polls this every 3 seconds.

    Response shape:
    {
      "status":   "queued" | "running" | "done" | "error",
      "step":     str,
      "pct":      int,
      "error":    str | null,
      "filename": str | null,   # only when done
    }
    Note: docx_b64 is NOT returned here (too large). Use /download/{job_id}.
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JSONResponse({
        "status":   job["status"],
        "step":     job["step"],
        "pct":      job["pct"],
        "error":    job["error"],
        "filename": job["filename"],
    })


@app.get("/download/{job_id}")
async def download(job_id: str):
    """
    Returns the finished DOCX as a binary download.
    Only available when status == "done".
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not finished yet.")
    if not job["docx_b64"]:
        raise HTTPException(status_code=500, detail="No document data available.")

    docx_bytes = base64.b64decode(job["docx_b64"])
    filename   = job["filename"] or "Customer_Profile.docx"

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
async def health():
    ntthai_ok = bool(os.getenv("NTTHAI_API_ID", "") and os.getenv("NTTHAI_API_SECRET", ""))
    active_jobs    = sum(1 for j in _JOBS.values() if j["status"] == "running")
    queued_jobs    = sum(1 for j in _JOBS.values() if j["status"] == "queued")
    return {
        "status"           : "ok",
        "active_llm"       : "ntthai_claude_sonnet" if ntthai_ok else "none",
        "ntthai_configured": ntthai_ok,
        "ntthai_model"     : os.getenv("NTTHAI_MODEL", "claude-sonnet-4-5"),
        "active_jobs"      : active_jobs,
        "queued_jobs"      : queued_jobs,
        "total_jobs"       : len(_JOBS),
    }


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        timeout_keep_alive=600,
    )