# Transcript → Customer Profile Generator
### FastAPI · LangChain · Groq · LLaMA 3.3 70B

Converts multiple discovery-call transcript files (`.vtt`, `.docx`, `.txt`) into a
fully-filled **SAP Customer Discovery Profile** Word document — powered by
**Groq's LLaMA 3.3 70B** (llama-3.3-70b-versatile), the fastest open-weight LLM available.

---

## Quick Start

```bash
# 1 · Install dependencies
pip install -r requirements.txt

# 2 · Add your API key
#     Edit .env → set ANTHROPIC_API_KEY=sk-ant-...

# 3 · Run
python main.py
# or
uvicorn main:app --reload --port 8000

# 4 · Open browser
#     http://localhost:8000
```

---

## Project Structure

```
transcript-fastapi/
├── main.py          # FastAPI app, routes, SSE pipeline
├── tools.py         # LangChain @tool functions (parse_vtt, parse_docx, chunk_text)
├── docx_builder.py  # python-docx Word document builder
├── index.html       # Frontend UI (served by FastAPI)
├── .env             # API keys — never commit this
└── requirements.txt
```

---

## How the Pipeline Works

```
Upload files
     │
     ▼
parse_vtt / parse_docx / txt    ← LangChain @tool
     │
     ▼
chunk_text (32k chars, 500 overlap)  ← LangChain RecursiveCharacterTextSplitter
     │
     ▼
extract_chunk × N  (parallel, max 3 concurrent)  ← ChatAnthropic
     │
     ▼
merge_chunk_results
     │
     ▼
synthesize  (de-duplicate & clean)  ← ChatAnthropic
     │
     ▼
build_docx  ← python-docx
     │
     ▼
SSE → browser download
```

---

## Template Sections Filled (60+ fields)

| # | Workstream |
|---|-----------|
| 1 | Customer / Business Overview (17 fields) |
| 2 | Idea to Market (I2M) |
| 3 | Source to Pay (S2P) |
| 4 | Plan to Produce (P2P) |
| 5 | Detect to Correct (D2C) |
| 6 | Forecast to Fulfill (F2F) |
| 7 | Warehouse Execution (WM/EWM) |
| 8 | Lead to Cash (L2C) |
| 9 | Logistics Planning & Transportation (TM) |
| 10 | Request to Service (R2S) |
| 11 | Record to Report (R2R) |
| 12 | Acquire to Dispose (A2D) |
| 13 | ESG Processes |
| 14 | Hire to Retire (H2R) |
| 15 | Enterprise Reporting & Data Analytics |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | **Required** — get free at console.groq.com | — |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |

## Why Groq + LLaMA 3.3 70B?

- **Speed** — Groq's LPU hardware runs LLaMA 3.3 70B at ~1000 tokens/sec, far faster than any cloud LLM API
- **Free tier** — generous free quota at console.groq.com
- **128k context** — handles large transcript chunks without truncation
- **Open weights** — no data retention by default
