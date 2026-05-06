# Sherlock AI VTT — Integration Guide

## Overview

Sherlock AI VTT is a live service hosted on Azure that converts transcript files (`.vtt`, `.docx`, `.txt`) into a structured **SAP Customer Discovery Profile JSON** — which can be merged directly into `master_data.json` in the Sherlock Web App, or downloaded as a Word document.

**Base URL:**
```
https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net
```

---

## Why This Integration Exists

The **Sherlock Web App** (Flask) processes `.docx` transcripts through a 3-step pipeline:

```
Step 1: .docx → parsed.json        (docx-to-parsed-json)
Step 2: parsed.json → master_data.json  (summarize-json)
Step 3: master_data.json → output .docx (process-json)
```

The problem: **Step 1 only accepts `.docx` files**. Teams meeting transcripts come as `.vtt` files, which that pipeline cannot handle.

**Sherlock AI VTT solves this.** It accepts `.vtt`, `.docx`, and `.txt` files and produces the same structured JSON that `master_data.json` expects — **completely bypassing Steps 1 and 2**. The output JSON can be merged into `master_data.json` and then fed directly into Step 3 to generate the Word document.

```
Teams .vtt files
      │
      ▼
Sherlock AI VTT API  ──→  structured JSON
                                │
                                ▼
                        merge into master_data.json
                                │
                                ▼
                    Step 3: process-json → output .docx
```

---

## All API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Check server is alive |
| `POST` | `/process` | Upload transcript files, start background job, get `job_id` |
| `GET` | `/status/{job_id}` | Poll job progress |
| `GET` | `/json/{job_id}` | **Get extracted JSON** (for integration with other apps) |
| `GET` | `/download/{job_id}` | Download the generated `.docx` (for standalone use) |

---

## API Endpoints Reference

### `GET /health`

Check that the server is running.

```bash
curl https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/health
```

**Response:**
```json
{ "status": "ok" }
```

---

### `POST /process`

Upload one or more transcript files. Returns a `job_id` immediately — processing runs in the background.

| Property | Value |
|---|---|
| Method | `POST` |
| Content-Type | `multipart/form-data` |
| Field name | `files` (repeat for multiple files) |
| Accepted formats | `.vtt`, `.docx`, `.txt`, `.doc`, `.md` |

**Request:**
```bash
curl -X POST https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/process \
  -F "files=@meeting.vtt" \
  -F "files=@notes.docx"
```

**Response:**
```json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000" }
```

**Error responses:**

| Status | Reason |
|---|---|
| `400` | No files provided |

---

### `GET /status/{job_id}`

Poll this every 3 seconds to track job progress.

```bash
curl https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/status/{job_id}
```

**Response:**
```json
{
  "status":   "running",
  "step":     "Analyzing chunk 2/4 with NTTHAI Claude Sonnet…",
  "pct":      45,
  "error":    null,
  "filename": null
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `queued` / `running` / `done` / `error` |
| `step` | string | Human-readable current step |
| `pct` | int | Progress percentage (0–100) |
| `error` | string \| null | Error message if `status == "error"` |
| `filename` | string \| null | Output filename when `status == "done"` |

**Error responses:**

| Status | Reason |
|---|---|
| `404` | Invalid or expired `job_id` |

---

### `GET /json/{job_id}`

**Primary endpoint for Flask app integration.**

Returns the extracted and synthesized structured JSON. Use this to merge transcript data into `master_data.json` — bypassing Steps 1 and 2 of the existing pipeline. Only available when `status == "done"`.

```bash
curl https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/json/{job_id}
```

**Response structure:**
```json
{
  "client_name": "Acme Corporation",
  "document_date": "06 April 2026",
  "General_Business_Overview": {
    "Schedule_of_Events":                       { "content": "..." },
    "Contacts_Identified":                      { "content": "..." },
    "Industry_Categorization":                  { "content": "..." },
    "Revenue_Band":                             { "content": "..." },
    "Legal_Entities_and_Names":                 { "content": "..." },
    "Business_Locations":                       { "content": "..." },
    "Fiscal_Year_Format":                       { "content": "..." },
    "Total_SAP_Users":                          { "content": "..." },
    "System_Landscape":                         { "content": "..." },
    "Key_Value_Drivers":                        { "content": "..." },
    "Motivations_for_Transformation":           { "content": "..." },
    "Areas_of_Perceived_Competitive_Advantage": { "content": "..." },
    "Perceived_Change_Resistance":              { "content": "..." },
    "Technical_Challenges_and_Requirements":    { "content": "..." },
    "Regulatory_Compliance_Requirements":       { "content": "..." },
    "Transformation_Program_C_Suite_KPIs":      { "content": "..." },
    "Key_Public_Cloud_Disqualifiers":           { "content": "..." }
  },
  "Idea_to_Market": {
    "Current_Processes_Key_Findings": { "content": "..." },
    "Pain_Points":                    { "content": "..." },
    "Proposed_SAP_Solutions_Mapping": { "content": "..." },
    "Major_Gaps_and_Integrations":    { "content": "..." }
  },
  "Source_to_Pay_S2P":                             { "...": "same 4 fields" },
  "Plan_to_Produce_P2P":                           { "...": "same 4 fields" },
  "Detect_to_Correct_D2C":                         { "...": "same 4 fields" },
  "Forecast_to_Fulfill_F2F":                       { "...": "same 4 fields" },
  "Warehouse_Execution_WM_EWM":                    { "...": "same 4 fields" },
  "Lead_to_Cash_L2C":                              { "...": "same 4 fields" },
  "Logistics_Planning_and_Transportation_TM":      { "...": "same 4 fields" },
  "Request_to_Service_R2S":                        { "...": "same 4 fields" },
  "Record_to_Report_R2R":                          { "...": "same 4 fields" },
  "Acquire_to_Dispose_A2D":                        { "...": "same 4 fields" },
  "Environmental_Social_and_Governance_ESG_Processes": { "...": "same 4 fields" },
  "Hire_to_Retire_H2R":                            { "...": "same 4 fields" },
  "Enterprise_Reporting_Data_and_Analytics_Strategy": { "...": "same 4 fields" }
}
```

**Error responses:**

| Status | Reason |
|---|---|
| `400` | Job not finished yet |
| `404` | Invalid or expired `job_id` |
| `500` | No JSON data available |

---

### `GET /download/{job_id}`

Download the generated `.docx` file (for standalone use, not needed in the Flask integration). Only available when `status == "done"`.

```bash
curl -O -J https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/download/{job_id}
```

**Response:** Binary `.docx` file.

**Error responses:**

| Status | Reason |
|---|---|
| `400` | Job not finished yet |
| `404` | Invalid or expired `job_id` |
| `500` | Document data missing |

---

## Integrating into the Sherlock Flask Web App

### How to merge the JSON into `master_data.json`

The JSON returned by `/json/{job_id}` has the same `{ section: { field: { content } } }` structure as `master_data.json`. Merging works by appending content for each field:

```python
def merge_vtt_json_into_master(master: dict, vtt_json: dict) -> dict:
    """
    Merge Sherlock AI VTT output into the existing master_data.json structure.
    Appends new content to existing content — does not overwrite.
    """
    import copy
    result = copy.deepcopy(master)

    for section, fields in vtt_json.items():
        if section in ("client_name", "document_date"):
            if not result.get(section):
                result[section] = fields
            continue

        if not isinstance(fields, dict):
            continue

        if section not in result:
            result[section] = {}

        for field, value in fields.items():
            new_content = value.get("content", "").strip() if isinstance(value, dict) else str(value).strip()
            if not new_content:
                continue

            existing = result[section].get(field, {})
            existing_content = existing.get("content", "").strip() if isinstance(existing, dict) else ""

            if existing_content:
                result[section][field] = {"content": existing_content + "\n\n" + new_content}
            else:
                result[section][field] = {"content": new_content}

    return result
```

---

### Full helper module — `sherlock_vtt_client.py`

Add this file to the Sherlock Flask Web App project:

```python
import time
import requests

VTT_API_BASE = "https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net"

def get_vtt_json(file_paths: list[str]) -> dict:
    """
    Upload transcript files (.vtt / .docx / .txt) to Sherlock AI VTT,
    wait for processing, and return the extracted structured JSON.
    This JSON can be merged directly into master_data.json.
    """
    files = [("files", (fp.split("/")[-1], open(fp, "rb"))) for fp in file_paths]
    r = requests.post(f"{VTT_API_BASE}/process", files=files, timeout=60)
    r.raise_for_status()
    job_id = r.json()["job_id"]

    while True:
        s = requests.get(f"{VTT_API_BASE}/status/{job_id}", timeout=10).json()
        if s["status"] == "done":
            break
        if s["status"] == "error":
            raise Exception(f"Sherlock VTT error: {s['error']}")
        time.sleep(3)

    result = requests.get(f"{VTT_API_BASE}/json/{job_id}", timeout=30)
    result.raise_for_status()
    return result.json()


def merge_vtt_json_into_master(master: dict, vtt_json: dict) -> dict:
    import copy
    result = copy.deepcopy(master)

    for section, fields in vtt_json.items():
        if section in ("client_name", "document_date"):
            if not result.get(section):
                result[section] = fields
            continue
        if not isinstance(fields, dict):
            continue
        if section not in result:
            result[section] = {}
        for field, value in fields.items():
            new_content = value.get("content", "").strip() if isinstance(value, dict) else str(value).strip()
            if not new_content:
                continue
            existing = result[section].get(field, {})
            existing_content = existing.get("content", "").strip() if isinstance(existing, dict) else ""
            if existing_content:
                result[section][field] = {"content": existing_content + "\n\n" + new_content}
            else:
                result[section][field] = {"content": new_content}

    return result
```

---

### Flask route — handling VTT transcript uploads

In `app.py` of the Sherlock Flask Web App, add this logic to the `/generate` route (or as a separate route) to handle `.vtt` files:

```python
import json
from sherlock_vtt_client import get_vtt_json, merge_vtt_json_into_master

def pipeline_thread(job_id, prospect_name, file_paths):
    """
    Modified pipeline that routes .vtt files through Sherlock AI VTT API
    and merges the result into master_data.json, then runs Step 3.
    """
    set_job(job_id, step=1, status="running", message="Checking file types...")

    vtt_files  = [f for f in file_paths if f.lower().endswith(".vtt")]
    docx_files = [f for f in file_paths if f.lower().endswith(".docx")]

    # ── Load existing master_data.json from Azure (if any) ────────────────
    master_data = {}
    master_blob = f"{prospect_name}/input/master_data.json"
    try:
        existing = download_blob_to_string(master_blob)   # your existing Azure helper
        master_data = json.loads(existing)
    except Exception:
        pass

    # ── Process .vtt files via Sherlock AI VTT API ─────────────────────────
    if vtt_files:
        set_job(job_id, step=1, status="running", message="Processing Teams transcripts via Sherlock AI VTT...")
        try:
            vtt_json = get_vtt_json(vtt_files)
            master_data = merge_vtt_json_into_master(master_data, vtt_json)
        except Exception as e:
            set_job(job_id, status="error", message=f"VTT processing failed: {e}")
            return

    # ── Process .docx files through the existing Steps 1 & 2 ──────────────
    if docx_files:
        set_job(job_id, step=1, status="running", message="Converting DOCX to JSON...")
        # ... existing Step 1 & 2 logic here, merge result into master_data ...

    # ── Save updated master_data.json to Azure ─────────────────────────────
    upload_string_to_blob(master_blob, json.dumps(master_data, indent=2))  # your existing Azure helper

    # ── Step 3: Generate Word document ────────────────────────────────────
    set_job(job_id, step=3, status="running", message="Generating Word document...")
    response = requests.post(FASTAPI_ENDPOINT_3, json={"summarized_data": master_data}, timeout=300)
    # ... rest of existing Step 3 logic ...
```

---

## Full Flow Diagram

```
Sherlock Flask Web App (port 5001)
         │
         │  User uploads files (mix of .vtt and .docx)
         │
         ▼
   Detect file types
         │
    ┌────┴──────────────┐
    │                   │
  .vtt files         .docx files
    │                   │
    ▼                   ▼
Sherlock AI         Existing pipeline
VTT API             Steps 1 & 2
(Azure)             (FastAPI port 5050)
    │                   │
    │  /process         │
    │  /status poll     │
    │  /json            │
    │                   │
    └─────┬─────────────┘
          │
          ▼
   merge into master_data.json
   (save to Azure Blob Storage)
          │
          ▼
   Step 3: process-json
   (FastAPI port 5050)
          │
          ▼
   output .docx saved to Azure
   output/{prospect}_{timestamp}.docx
```

---

## Notes

- Jobs are kept in memory for **1 hour** then auto-deleted
- Multiple files can be uploaded in a single request — all merged before processing
- Supported input formats: `.vtt`, `.docx`, `.txt`, `.doc`, `.md`
- Processing time: ~1–5 minutes depending on transcript length
- The `/json` endpoint returns data only — no Word document is generated, saving time when integrating
