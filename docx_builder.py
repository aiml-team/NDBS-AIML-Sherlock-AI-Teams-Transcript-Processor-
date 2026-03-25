"""
docx_builder.py
===============
Renders the filled Customer Profile DOCX by:
  1. Loading word_template.docx via docxtpl (Jinja2 template engine)
  2. Injecting the extracted JSON data directly into the template placeholders
  3. Updating the cover-page client name and date fields

The template already has the exact styling — this module just fills content.
"""

import io
import os
import re
from datetime import datetime
from docxtpl import DocxTemplate


def _safe_content(value) -> str:
    """Return a clean string for any value that might come from the JSON."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(str(i) for i in value)
    if isinstance(value, dict):
        if "content" in value:
            return _safe_content(value["content"])
        return "\n".join(f"{k}: {v}" for k, v in value.items())
    return str(value)


def _section(raw_dict: dict) -> dict:
    """Ensure every field in a workstream section has a clean 'content' string."""
    fields = [
        "Current_Processes_Key_Findings",
        "Pain_Points",
        "Proposed_SAP_Solutions_Mapping",
        "Major_Gaps_and_Integrations",
    ]
    out = {}
    for f in fields:
        val = raw_dict.get(f, {})
        content = _safe_content(val.get("content", "") if isinstance(val, dict) else val)
        out[f] = {"content": content or "Not identified in transcripts."}
    return out


def _gbo(raw_dict: dict) -> dict:
    """Build the General_Business_Overview context block."""
    fields = [
        "Schedule_of_Events", "Contacts_Identified", "Industry_Categorization",
        "Revenue_Band", "Legal_Entities_and_Names", "Business_Locations",
        "Fiscal_Year_Format", "Total_SAP_Users", "System_Landscape",
        "Key_Value_Drivers", "Motivations_for_Transformation",
        "Areas_of_Perceived_Competitive_Advantage", "Perceived_Change_Resistance",
        "Technical_Challenges_and_Requirements", "Regulatory_Compliance_Requirements",
        "Transformation_Program_C_Suite_KPIs", "Key_Public_Cloud_Disqualifiers",
    ]
    out = {}
    for f in fields:
        val = raw_dict.get(f, {})
        content = _safe_content(val.get("content", "") if isinstance(val, dict) else val)
        out[f] = {"content": content or "Not identified in transcripts."}
    return out


def build_docx(data: dict, template_path: str | None = None) -> bytes:
    """
    Render the template with extracted data and return the DOCX as bytes.

    `data` must match the TEMPLATE_SCHEMA structure from tools.py.
    `template_path` should point to word_template.docx.
    """
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(
            f"word_template.docx not found at: {template_path}\n"
            "Place word_template.docx in the same folder as main.py."
        )

    tpl = DocxTemplate(template_path)

    client_name = _safe_content(data.get("client_name", "")) or "Client Name"
    doc_date    = _safe_content(data.get("document_date", "")) or \
                  datetime.now().strftime("%d %B %Y")

    # Build the full Jinja2 context — mirrors {{ data.SECTION.FIELD.content }}
    context = {
        "data": {
            "General_Business_Overview": _gbo(
                data.get("General_Business_Overview", {})),

            "Idea_to_Market": _section(
                data.get("Idea_to_Market", {})),
            "Source_to_Pay_S2P": _section(
                data.get("Source_to_Pay_S2P", {})),
            "Plan_to_Produce_P2P": _section(
                data.get("Plan_to_Produce_P2P", {})),
            "Detect_to_Correct_D2C": _section(
                data.get("Detect_to_Correct_D2C", {})),
            "Forecast_to_Fulfill_F2F": _section(
                data.get("Forecast_to_Fulfill_F2F", {})),
            "Warehouse_Execution_WM_EWM": _section(
                data.get("Warehouse_Execution_WM_EWM", {})),
            "Lead_to_Cash_L2C": _section(
                data.get("Lead_to_Cash_L2C", {})),
            "Logistics_Planning_and_Transportation_TM": _section(
                data.get("Logistics_Planning_and_Transportation_TM", {})),
            "Request_to_Service_R2S": _section(
                data.get("Request_to_Service_R2S", {})),
            "Record_to_Report_R2R": _section(
                data.get("Record_to_Report_R2R", {})),
            "Acquire_to_Dispose_A2D": _section(
                data.get("Acquire_to_Dispose_A2D", {})),
            "Environmental_Social_and_Governance_ESG_Processes": _section(
                data.get("Environmental_Social_and_Governance_ESG_Processes", {})),
            "Hire_to_Retire_H2R": _section(
                data.get("Hire_to_Retire_H2R", {})),
            "Enterprise_Reporting_Data_and_Analytics_Strategy": _section(
                data.get("Enterprise_Reporting_Data_and_Analytics_Strategy", {})),
        }
    }

    tpl.render(context)

    # ── Patch the cover page fields (client name & date) ──────────────────
    # The cover table has static text "Client's full name" and a date field.
    # We find those runs in the rendered XML and replace their text.
    _patch_cover(tpl, client_name, doc_date)

    buf = io.BytesIO()
    tpl.save(buf)
    return buf.getvalue()


def _patch_cover(tpl: DocxTemplate, client_name: str, doc_date: str):
    """
    Replace the cover page placeholder texts with real client name and date.
    Operates directly on the rendered XML.
    """
    from lxml import etree
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    body = tpl.docx.element.body

    # Walk all paragraphs in tables (cover is a table)
    for tbl in body.iter("{%s}tbl" % W):
        for p in tbl.iter("{%s}p" % W):
            # Collect full text of paragraph
            texts = [r.text or "" for r in p.iter("{%s}t" % W)]
            full  = "".join(texts)

            # Replace "Client's full name" with actual client name
            if "Client" in full and ("full name" in full or "name" in full.lower()):
                _replace_para_text(p, W, client_name)

            # Replace "FirstName LastName"
            elif full.strip() == "FirstName LastName":
                _replace_para_text(p, W, "")   # leave blank or put author

            # Replace the date field text (keeps the field, updates cached value)
            elif re.search(r"\d{1,2}\s+\w+\s+\d{4}", full):
                # Update the cached date text inside the field
                for t in p.iter("{%s}t" % W):
                    if t.text and re.search(r"\d{1,2}\s+\w+\s+\d{4}", t.text):
                        t.text = doc_date
                        break


def _replace_para_text(para, W: str, new_text: str):
    """Replace all <w:t> text runs in a paragraph with a single new text run."""
    runs = list(para.iter("{%s}r" % W))
    if not runs:
        return
    # Clear all runs except first, set first run's text
    first_t = runs[0].find("{%s}t" % W)
    if first_t is None:
        from lxml import etree
        first_t = etree.SubElement(runs[0], "{%s}t" % W)
    first_t.text = new_text
    if new_text and (new_text.startswith(" ") or new_text.endswith(" ")):
        first_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    # Remove subsequent runs
    for r in runs[1:]:
        r.getparent().remove(r)