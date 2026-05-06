# Sherlock AI VTT — Developer Integration Guide

> Step-by-step guide for integrating the Sherlock AI VTT API into another application.

**Live API Base URL:**
```
https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net
```

---

## What This API Does

You send transcript files (Teams `.vtt`, `.docx`, `.txt`) to this API.
It processes them with AI and returns either:

- A **structured JSON** (for integrating into another pipeline)
- A **Word document** (for direct download)

---

## Quick Overview of All Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Check API is alive |
| `POST` | `/process` | Upload files → get `job_id` |
| `GET` | `/status/{job_id}` | Check job progress |
| `GET` | `/json/{job_id}` | Get extracted JSON result |
| `GET` | `/download/{job_id}` | Download generated `.docx` |

---

## Step-by-Step Integration

### Step 1 — Check the API is alive

Before doing anything, confirm the API is reachable.

**Request:**
```
GET /health
```

**Response:**
```json
{ "status": "ok" }
```

If you get anything other than `"status": "ok"`, stop — the API is down.

---

### Step 2 — Upload your transcript files

Send your files as `multipart/form-data`. You can upload one or multiple files in a single request. The API starts processing in the background and immediately returns a `job_id`.

**Request:**
```
POST /process
Content-Type: multipart/form-data

Field name: files  (repeat for each file)
Accepted:   .vtt, .docx, .txt, .doc, .md
```

**Example — curl:**
```bash
curl -X POST https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net/process \
  -F "files=@transcript.vtt" \
  -F "files=@meeting_notes.docx"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Save this `job_id` — you will need it for all subsequent steps.

**Error:**

| HTTP Status | Reason |
|-------------|--------|
| `400` | No files were provided |

---

### Step 3 — Poll for job completion

Processing takes 1–5 minutes depending on the size of the transcript. Poll this endpoint every 3 seconds until `status` becomes `"done"` or `"error"`.

**Request:**
```
GET /status/{job_id}
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

**Status values:**

| Value | Meaning | What to do |
|-------|---------|------------|
| `queued` | Waiting to start | Keep polling |
| `running` | Processing | Keep polling |
| `done` | Finished | Proceed to Step 4 |
| `error` | Failed | Read `error` field, stop |

**When done**, `filename` will contain the output filename e.g. `Acme_Corp_Discovery_Profile.docx`.

**Errors:**

| HTTP Status | Reason |
|-------------|--------|
| `404` | Invalid or expired `job_id` |

---

### Step 4A — Get the JSON result (for pipeline integration)

Use this when you want to feed the extracted data into your own pipeline (e.g. merge into `master_data.json`).

**Request:**
```
GET /json/{job_id}
```

**Response — full structure:**
```json
{
  "client_name": "Acme Corporation",
  "document_date": "06 April 2026",

  "General_Business_Overview": {
    "Schedule_of_Events":                       { "content": "Discovery call held on 1 April 2026..." },
    "Contacts_Identified":                      { "content": "John Smith - CIO, jane@acme.com..." },
    "Industry_Categorization":                  { "content": "Manufacturing" },
    "Revenue_Band":                             { "content": "€500M - €1B" },
    "Legal_Entities_and_Names":                 { "content": "Acme Corp GmbH, Acme UK Ltd" },
    "Business_Locations":                       { "content": "Germany, UK, USA" },
    "Fiscal_Year_Format":                       { "content": "January - December" },
    "Total_SAP_Users":                          { "content": "~1200 users" },
    "System_Landscape":                         { "content": "SAP ECC 6.0, legacy WM..." },
    "Key_Value_Drivers":                        { "content": "Cost reduction, real-time visibility..." },
    "Motivations_for_Transformation":           { "content": "ECC end of maintenance in 2027..." },
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

  "Source_to_Pay_S2P":                              { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Plan_to_Produce_P2P":                            { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Detect_to_Correct_D2C":                          { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Forecast_to_Fulfill_F2F":                        { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Warehouse_Execution_WM_EWM":                     { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Lead_to_Cash_L2C":                               { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Logistics_Planning_and_Transportation_TM":       { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Request_to_Service_R2S":                         { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Record_to_Report_R2R":                           { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Acquire_to_Dispose_A2D":                         { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Environmental_Social_and_Governance_ESG_Processes": { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Hire_to_Retire_H2R":                             { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } },
  "Enterprise_Reporting_Data_and_Analytics_Strategy": { "Current_Processes_Key_Findings": { "content": "..." }, "Pain_Points": { "content": "..." }, "Proposed_SAP_Solutions_Mapping": { "content": "..." }, "Major_Gaps_and_Integrations": { "content": "..." } }
}
```

Every field follows the same pattern:
```json
{ "content": "text extracted from transcript, empty string if not found" }
```

**Errors:**

| HTTP Status | Reason |
|-------------|--------|
| `400` | Job not finished yet |
| `404` | Invalid or expired `job_id` |
| `500` | No data available |

---

### Step 4B — Download the Word document (for standalone use)

Use this when you just want the finished `.docx` file directly.

**Request:**
```
GET /download/{job_id}
```

**Response:** Binary `.docx` file with headers:
```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="Acme_Corp_Discovery_Profile.docx"
```

**Errors:**

| HTTP Status | Reason |
|-------------|--------|
| `400` | Job not finished yet |
| `404` | Invalid or expired `job_id` |
| `500` | No document data |

---

## Ready-to-Use Code

### Python (requests)

Copy this helper into your project:

```python
import time
import requests

BASE_URL = "https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net"


def sherlock_get_json(file_paths: list) -> dict:
    """Upload transcript files and return the extracted JSON."""

    # Upload
    files = [("files", (fp.split("/")[-1], open(fp, "rb"))) for fp in file_paths]
    r = requests.post(f"{BASE_URL}/process", files=files, timeout=60)
    r.raise_for_status()
    job_id = r.json()["job_id"]

    # Poll
    while True:
        s = requests.get(f"{BASE_URL}/status/{job_id}", timeout=10).json()
        if s["status"] == "done":
            break
        if s["status"] == "error":
            raise Exception(f"Sherlock AI error: {s['error']}")
        time.sleep(3)

    # Get JSON
    result = requests.get(f"{BASE_URL}/json/{job_id}", timeout=30)
    result.raise_for_status()
    return result.json()


def sherlock_get_docx(file_paths: list) -> tuple:
    """Upload transcript files and return (docx_bytes, filename)."""

    # Upload
    files = [("files", (fp.split("/")[-1], open(fp, "rb"))) for fp in file_paths]
    r = requests.post(f"{BASE_URL}/process", files=files, timeout=60)
    r.raise_for_status()
    job_id = r.json()["job_id"]

    # Poll
    while True:
        s = requests.get(f"{BASE_URL}/status/{job_id}", timeout=10).json()
        if s["status"] == "done":
            filename = s["filename"]
            break
        if s["status"] == "error":
            raise Exception(f"Sherlock AI error: {s['error']}")
        time.sleep(3)

    # Download
    docx = requests.get(f"{BASE_URL}/download/{job_id}", timeout=60)
    docx.raise_for_status()
    return docx.content, filename


# --- Usage ---

# Get JSON (for pipeline integration)
data = sherlock_get_json(["meeting.vtt", "notes.docx"])
print(data["client_name"])
print(data["General_Business_Overview"]["Contacts_Identified"]["content"])

# Get DOCX (for direct download)
docx_bytes, filename = sherlock_get_docx(["meeting.vtt"])
with open(filename, "wb") as f:
    f.write(docx_bytes)
```

---

### Flask app integration

Add `sherlock_vtt_client.py` to your Flask project:

```python
import time
import copy
import requests

BASE_URL = "https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net"


def get_vtt_json(file_paths: list) -> dict:
    files = [("files", (fp.split("/")[-1], open(fp, "rb"))) for fp in file_paths]
    r = requests.post(f"{BASE_URL}/process", files=files, timeout=60)
    r.raise_for_status()
    job_id = r.json()["job_id"]

    while True:
        s = requests.get(f"{BASE_URL}/status/{job_id}", timeout=10).json()
        if s["status"] == "done":
            break
        if s["status"] == "error":
            raise Exception(f"Sherlock VTT error: {s['error']}")
        time.sleep(3)

    result = requests.get(f"{BASE_URL}/json/{job_id}", timeout=30)
    result.raise_for_status()
    return result.json()


def merge_into_master(master: dict, vtt_json: dict) -> dict:
    """Merge VTT JSON into existing master_data.json. Appends, never overwrites."""
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

Use it in your Flask pipeline:

```python
from sherlock_vtt_client import get_vtt_json, merge_into_master

# Separate files by type
vtt_files  = [f for f in uploaded_paths if f.endswith(".vtt")]
docx_files = [f for f in uploaded_paths if f.endswith(".docx")]

# Load existing master_data (from Azure or elsewhere)
master_data = load_master_data(prospect_name) or {}

# Process VTT files through Sherlock AI VTT
if vtt_files:
    vtt_json    = get_vtt_json(vtt_files)
    master_data = merge_into_master(master_data, vtt_json)

# Process DOCX files through existing Steps 1 & 2
if docx_files:
    # ... your existing pipeline logic ...
    pass

# Save updated master_data
save_master_data(prospect_name, master_data)

# Run Step 3 to generate Word document
generate_docx(master_data)
```

---

### JavaScript / Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const BASE_URL = 'https://ndbs-aiml-sherlockaiteamstranscript-ewgucedve0cad6e2.westeurope-01.azurewebsites.net';

async function sherlockGetJson(filePaths) {
    const form = new FormData();
    for (const fp of filePaths) {
        form.append('files', fs.createReadStream(fp));
    }

    const { data: { job_id } } = await axios.post(`${BASE_URL}/process`, form, {
        headers: form.getHeaders(), timeout: 60000,
    });

    while (true) {
        const { data: s } = await axios.get(`${BASE_URL}/status/${job_id}`);
        if (s.status === 'done') break;
        if (s.status === 'error') throw new Error(s.error);
        await new Promise(r => setTimeout(r, 3000));
    }

    const { data } = await axios.get(`${BASE_URL}/json/${job_id}`);
    return data;
}

// Usage
const result = await sherlockGetJson(['meeting.vtt', 'notes.docx']);
console.log(result.client_name);
console.log(result.General_Business_Overview.Contacts_Identified.content);
```

---

## How the JSON maps to master_data.json

The JSON returned by `/json/{job_id}` is structured identically to `master_data.json`:

```
JSON key                                     → master_data.json section
─────────────────────────────────────────────────────────────────────
client_name                                  → cover page client name
General_Business_Overview.Contacts_Identified.content  → section field
Idea_to_Market.Pain_Points.content           → section field
Source_to_Pay_S2P.Current_Processes_Key_Findings.content → section field
... (same pattern for all 14 workstreams)
```

Every workstream section has exactly these 4 fields:
- `Current_Processes_Key_Findings`
- `Pain_Points`
- `Proposed_SAP_Solutions_Mapping`
- `Major_Gaps_and_Integrations`

Empty fields are returned as `{ "content": "" }` — never null.

---

## Full Flow (with Flask Web App)

```
User uploads .vtt + .docx files
            │
            ▼
      Flask Web App
            │
    ┌───────┴───────────┐
    │                   │
  .vtt files         .docx files
    │                   │
    ▼                   ▼
Sherlock AI VTT     Existing Steps
API (this API)      1 & 2 (FastAPI)
    │                   │
    └───────┬───────────┘
            │
            ▼
   merge_into_master()
            │
            ▼
    save master_data.json
    to Azure Blob Storage
            │
            ▼
      Step 3 (FastAPI)
   process-json endpoint
            │
            ▼
   output .docx saved to Azure
```

---

## Important Notes

| Topic | Detail |
|-------|--------|
| Job expiry | Jobs are held in memory for **1 hour** then deleted |
| Multiple files | All files in one request are merged before processing |
| Empty fields | Fields not found in transcript return `{ "content": "" }` |
| Processing time | ~1–5 minutes depending on transcript length |
| `/json` vs `/download` | Use `/json` for pipeline integration, `/download` for direct file download |
| CORS | If calling from a browser on a different domain, CORS headers must be enabled on the server |
