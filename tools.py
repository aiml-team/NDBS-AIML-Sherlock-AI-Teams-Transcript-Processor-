"""
tools.py  –  LangChain tools + shared schema for transcript processing.

Transcript cleaning philosophy:
  REMOVE: timestamps, cue numbers, WEBVTT header, NOTE blocks, HTML tags
  KEEP:   every word spoken — speaker labels stripped but speech preserved
"""

import io
import re
import json
import logging
from typing import Optional

import mammoth
import webvtt
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


# ── Transcript cleaning helpers ───────────────────────────────────────────────

# Matches VTT/SRT timestamps:  00:00:01.000 --> 00:00:04.500
#                              0:01.000 --> 0:04.500
_TS_PATTERN = re.compile(
    r"^\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[.,]\d{3}"
    r"|^\d{1,2}:\d{2}[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}[.,]\d{3}"
)

def _strip_tags_and_speakers(line: str) -> str:
    """
    Strip inline VTT/HTML tags and leading speaker labels from a line.
    The spoken words are always preserved.

    Examples:
      '<v John Smith>Hello there.</v>'  →  'Hello there.'
      '[Bob]: We use SAP ECC.'          →  'We use SAP ECC.'
      'John Smith: Hello there.'        →  'Hello there.'   (only if name-like)
      '<i>emphasis</i>'                 →  'emphasis'
    """
    # Remove all HTML/VTT tags  <v Speaker>, <c.color>, <i>, <b>, <u>, </v> …
    line = re.sub(r"<[^>]+>", "", line)
    # Remove speaker labels:  [Name]:  or  Name:  (only if looks like a name)
    line = re.sub(r"^\[?[A-Z][a-zA-Z .'\-]{1,40}\]?\s*:\s*", "", line)
    return line.strip()


def _deduplicate(lines: list[str]) -> list[str]:
    """Remove consecutive duplicate lines (rolling-caption artefact)."""
    out, prev = [], None
    for ln in lines:
        if ln != prev:
            out.append(ln)
        prev = ln
    return out


def _clean_transcript(raw: str) -> str:
    """
    Clean a raw transcript string (VTT or plain text).
    Removes: WEBVTT header, NOTE blocks, cue index numbers, timestamp lines,
             inline HTML/VTT tags, speaker labels, consecutive duplicates.
    Keeps:   every word of spoken dialogue.
    """
    lines = raw.splitlines()
    result = []
    skip_note = False

    for line in lines:
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            skip_note = False
            continue

        # Skip WEBVTT file header
        if stripped.upper().startswith("WEBVTT"):
            continue

        # Skip NOTE blocks (single-line or multi-line)
        if stripped.upper().startswith("NOTE"):
            skip_note = True
            continue
        if skip_note:
            continue

        # Skip pure timestamp lines
        if _TS_PATTERN.match(stripped):
            continue

        # Skip standalone cue index numbers  (e.g. "1", "42")
        if re.fullmatch(r"\d+", stripped):
            continue

        # Clean inline tags & speaker labels, then keep the speech
        cleaned = _strip_tags_and_speakers(stripped)
        if cleaned:
            result.append(cleaned)

    return "\n".join(_deduplicate(result))


# ── LangChain @tool functions ─────────────────────────────────────────────────

@tool
def parse_vtt(content: str) -> str:
    """
    Parse a WebVTT transcript file and return clean dialogue text.
    Removes timestamps, cue numbers, HTML tags, speaker labels and duplicates.
    All spoken words are preserved.
    """
    try:
        # Try webvtt library first (more accurate caption boundary detection)
        buf = io.StringIO(content)
        captions = webvtt.read_buffer(buf)
        lines = []
        for cap in captions:
            cleaned = _strip_tags_and_speakers(cap.text.replace("\n", " "))
            if cleaned:
                lines.append(cleaned)
        return "\n".join(_deduplicate(lines))
    except Exception:
        # Fallback: line-by-line manual clean
        return _clean_transcript(content)


@tool
def parse_docx(file_bytes_hex: str) -> str:
    """Extract plain text from a DOCX file given its bytes as a hex string."""
    raw = bytes.fromhex(file_bytes_hex)
    result = mammoth.extract_raw_text(io.BytesIO(raw))
    return result.value.strip()


@tool
def chunk_text(text: str, chunk_size: int = 20000, overlap: int = 400) -> str:
    """
    Split a long text into overlapping chunks for LLM processing.
    Returns a JSON list of chunk strings.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", " ", ""],
    )
    return json.dumps(splitter.split_text(text))


# ── JSON schema — mirrors every placeholder in word_template.docx ─────────────
#
# The LLM is asked to produce exactly this structure.
# Keys match the Jinja2 path:  data.<SECTION>.<FIELD>.content
#
TEMPLATE_SCHEMA = {
    "client_name": "",          # for the cover page
    "document_date": "",        # for the cover page

    "General_Business_Overview": {
        "Schedule_of_Events":                       {"content": ""},
        "Contacts_Identified":                      {"content": ""},
        "Industry_Categorization":                  {"content": ""},
        "Revenue_Band":                             {"content": ""},
        "Legal_Entities_and_Names":                 {"content": ""},
        "Business_Locations":                       {"content": ""},
        "Fiscal_Year_Format":                       {"content": ""},
        "Total_SAP_Users":                          {"content": ""},
        "System_Landscape":                         {"content": ""},
        "Key_Value_Drivers":                        {"content": ""},
        "Motivations_for_Transformation":           {"content": ""},
        "Areas_of_Perceived_Competitive_Advantage": {"content": ""},
        "Perceived_Change_Resistance":              {"content": ""},
        "Technical_Challenges_and_Requirements":    {"content": ""},
        "Regulatory_Compliance_Requirements":       {"content": ""},
        "Transformation_Program_C_Suite_KPIs":      {"content": ""},
        "Key_Public_Cloud_Disqualifiers":           {"content": ""},
    },
    "Idea_to_Market": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Source_to_Pay_S2P": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Plan_to_Produce_P2P": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Detect_to_Correct_D2C": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Forecast_to_Fulfill_F2F": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Warehouse_Execution_WM_EWM": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Lead_to_Cash_L2C": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Logistics_Planning_and_Transportation_TM": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Request_to_Service_R2S": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Record_to_Report_R2R": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Acquire_to_Dispose_A2D": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Environmental_Social_and_Governance_ESG_Processes": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Hire_to_Retire_H2R": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
    "Enterprise_Reporting_Data_and_Analytics_Strategy": {
        "Current_Processes_Key_Findings":  {"content": ""},
        "Pain_Points":                     {"content": ""},
        "Proposed_SAP_Solutions_Mapping":  {"content": ""},
        "Major_Gaps_and_Integrations":     {"content": ""},
    },
}

# ── LLM system prompts ────────────────────────────────────────────────────────

EXTRACTION_SYSTEM = f"""You are an expert SAP consultant analyst.
Extract information from customer discovery call transcripts.
Return ONLY a valid JSON object matching EXACTLY this structure:

{json.dumps(TEMPLATE_SCHEMA, indent=2)}

Rules:
- Use the exact same keys and nesting shown above.
- Set "content" to "" (empty string) for anything not mentioned in the transcript.
- Do NOT invent or hallucinate data.
- Be concise but complete — bullet points or short paragraphs are fine.
- For contacts, include name, title, email/phone if mentioned.
- For SAP solutions, use real SAP product names (S/4HANA, Ariba, SuccessFactors, etc.).
- Return only the JSON — no markdown fences, no preamble, no explanation.
"""

SYNTHESIS_SYSTEM = """You are an expert SAP consultant.
You have extracted data from multiple transcript chunks that may contain duplicates or partial information.
Synthesize into ONE clean JSON object with the exact same structure.
- Merge duplicates intelligently; remove redundancy.
- Produce clear, professional summaries.
- Keep empty fields as "".
- Return only the JSON — no markdown fences, no preamble.
"""


# ── Merge + normalise helpers ─────────────────────────────────────────────────

def _to_str(value) -> str:
    """Coerce any LLM-returned value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(", ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, dict):
        # If it has a 'content' key just return that
        if "content" in value:
            return _to_str(value["content"])
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def _merge_content(a: str, b: str) -> str:
    """Combine two content strings, avoiding exact duplicates."""
    a, b = a.strip(), b.strip()
    if not b or b == a:
        return a
    if not a:
        return b
    return a + "\n" + b


def merge_chunk_results(results: list[dict]) -> dict:
    """
    Deep-merge a list of per-chunk extraction dicts into one.
    Works with the nested TEMPLATE_SCHEMA structure.
    """
    import copy
    merged = copy.deepcopy(TEMPLATE_SCHEMA)

    for r in results:
        # Top-level scalar fields
        for key in ("client_name", "document_date"):
            val = _to_str(r.get(key, "")).strip()
            if val and not merged.get(key):
                merged[key] = val

        # Section dicts
        for section, fields in TEMPLATE_SCHEMA.items():
            if not isinstance(fields, dict):
                continue
            r_section = r.get(section, {}) or {}
            for field, _ in fields.items():
                r_field = r_section.get(field, {}) or {}
                new_val = _to_str(r_field.get("content", "") if isinstance(r_field, dict) else r_field).strip()
                existing = merged[section][field]["content"]
                merged[section][field]["content"] = _merge_content(existing, new_val)

    return merged


def _repair_truncated_json(text: str) -> str:
    """
    Attempt to repair a JSON string that was cut off mid-stream (token limit hit).

    Strategy:
    1. Truncate at the last complete key-value pair we can find.
    2. Close all open braces/brackets in reverse order.
    3. Return the repaired string for a second parse attempt.
    """
    # Remove trailing incomplete string: find last complete quoted value or number
    # by walking backwards to the last comma or colon that ended a clean value.
    text = text.rstrip()

    # Drop everything after the last complete value (last " or digit or } or ])
    # that is followed only by whitespace / partial keys
    cut = max(
        text.rfind('",'),
        text.rfind('",\n'),
        text.rfind("},"),
        text.rfind("},\n"),
        text.rfind("]},"),
    )
    if cut > 0:
        text = text[: cut + 1]   # keep up to and including the comma

    # Count open braces and brackets
    depth_brace   = text.count("{") - text.count("}")
    depth_bracket = text.count("[") - text.count("]")

    # Close open brackets first (innermost), then braces
    closing = "]" * max(0, depth_bracket) + "}" * max(0, depth_brace)
    return text + "\n" + closing


def safe_parse_json(text: str) -> dict:
    """
    Parse the first JSON object from an LLM response.

    Handles two cases:
    1. Valid JSON  → parsed directly.
    2. Truncated JSON (token limit hit mid-response) → repaired then parsed.
       Truncation shows up as JSONDecodeError with 'Expecting' in the message.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$",          "", text, flags=re.MULTILINE)

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {}

    raw_json = match.group()

    # ── First attempt: straight parse ────────────────────────────────────
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed (will attempt repair): %s", e)

    # ── Second attempt: repair truncated JSON then parse ─────────────────
    try:
        repaired = _repair_truncated_json(raw_json)
        result   = json.loads(repaired)
        logger.info("JSON repair succeeded — recovered partial chunk data")
        return result
    except json.JSONDecodeError as e2:
        logger.warning("JSON repair also failed: %s", e2)

    return {}