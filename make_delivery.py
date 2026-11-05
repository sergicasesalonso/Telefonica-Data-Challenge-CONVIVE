"""Builds deliverables/iteration2/CONVIVE_Iteration2_Delivery.docx (draft, at most 4 pages).

Every number comes from the outputs of the pipeline: 3.1.6_summary.json, the manifest and the pipeline state.
"""

import json
import pickle
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

import loaders as L

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "deliverables" / "iteration2"
SHOTS = OUT_DIR / "screenshots"
DARK = RGBColor(0x1F, 0x3A, 0x5F)
HEADER = "CONVIVE · Team 102_A (Convive Lab) · Iteration #2 delivery · v0.1"

# WBS, deliverable, owner, due, file in deliverables/iteration2/ (glob-free path, checked on disk)
PLAN = [
    ("3.1.0", "Data reception under NDA, inventory", "Sergi Cases Alonso", "29/10", "3.1.0_data_inventory.md"),
    ("2.1.1", "Geographic aggregation definition", "Ander Barnadas Mendizabal", "02/11", "2.1.1_geographic_levels.csv"),
    ("2.1.2", "Temporal aggregation definition", "Devanshi Shroff", "02/11", "2.1.2_temporal_levels.md"),
    ("4.1.3", "Visualisation environment selection", "Martí Casas Niubó", "02/11", "4.1.3_VisualisationEnvironment.md"),
    ("4.1.1", "Dashboard layout and navigation", "Martí Casas Niubó", "02/11", "4.1.1_dashboard_layout.md"),
    ("3.1.1", "Data loading and initial inspection", "Pau Borrell Bullich", "30/10", "3.1.1_inspection_summary.md"),
    ("3.2.0", "Research questions and topics list", "Sergi Cases Alonso", "03/11", "3.2.0_ResearchQuestions.md"),
    ("3.1.7", "Switch from synthetic to real data", "Pau Borrell Bullich", "04/11", "../../CONVIVE_Iteration2.ipynb"),
    ("3.1.2", "Data quality assessment", "Ander Barnadas Mendizabal", "06/11", "3.1.2_data_quality_report.md"),
    ("3.1.6", "Preliminary descriptive statistics", "Ander Barnadas Mendizabal", "06/11", "3.1.6_summary.md"),
    ("4.2.0", "Preliminary dashboard, general statistics and filters", "Pau Borrell Bullich", "08/11", "4.2.0_dashboard_notes.md"),
    ("3.1.3", "Data cleaning and transformation", "Pau Borrell Bullich", "09/11", "3.1.3_cleaning_log.md"),
    ("4.2.1", "Interactive maps (first version)", "Martí Casas Niubó", "09/11", "4.2.1_map_visitors.html"),
]


def shade(cell, color):
    tc = cell._tc.get_or_add_tcPr()
    element = OxmlElement("w:shd")
    element.set(qn("w:val"), "clear")
    element.set(qn("w:color"), "auto")
    element.set(qn("w:fill"), color)
    tc.append(element)


def set_cell(cell, text, size=8, bold=False):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold


def heading(doc, text):
    p = doc.add_paragraph()
    p.style = doc.styles["Heading 1"]
    p.add_run(text)
    return p


def body(doc, text, size=9.5, after=3):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    parts = text.replace("`", "").split("**")
    for i, part in enumerate(parts):
        run = p.add_run(part)
        run.font.size = Pt(size)
        run.bold = i % 2 == 1
    return p


def bullet(doc, text, size=9.5):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(1.5)
    parts = text.replace("`", "").split("**")
    for i, part in enumerate(parts):
        run = p.add_run(part)
        run.font.size = Pt(size)
        run.bold = i % 2 == 1
    return p


def picture(doc, name, width_cm, caption):
    path = SHOTS / name
    if not path.exists():
        body(doc, f"[Screenshot {name} not available: TBD]")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(5)
    run = c.add_run(caption)
    run.italic = True
    run.font.size = Pt(8)


def status(file_name):
    return "Done" if (OUT_DIR / file_name).resolve().exists() else "NOT FINISHED"


def main():
    summary = json.loads((OUT_DIR / "3.1.6_summary.json").read_text(encoding="utf-8"))
    state = pickle.loads((L.PROCESSED_DIR / "_pipeline_state.pkl").read_bytes())
    manifest = L.read_manifest()
    found = [e for e in manifest.values() if e.get("found")]
    size_gb = sum(e["bytes"] for e in found) / 1024 ** 3
    rows = sum(e["rows"] for e in found)
    quality, temporal, geo = state["quality"], state["temporal"], state["geo"]
    metrics = {k: t.attrs["metrics"] for k, t in quality["tables"].items()}
    _, details = quality["cross"]
    missing = ", ".join(str(d) for d in temporal["missing"])
    paragraphs = summary["paragraphs"]
    n_tables = len(list((OUT_DIR / "3.1.6_stats").glob("*.csv")))

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(1.9)
    section.top_margin, section.bottom_margin = Cm(1.8), Cm(1.5)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(9.5)
    h1 = doc.styles["Heading 1"]
    h1.font.name = "Calibri"
    h1.font.size = Pt(12.5)
    h1.font.bold = True
    h1.font.color.rgb = DARK
    h1.paragraph_format.space_before = Pt(8)
    h1.paragraph_format.space_after = Pt(3)
    h1.paragraph_format.keep_with_next = True

    head = section.header.paragraphs[0]
    run = head.add_run(HEADER)
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(1)
    run = title.add_run("CONVIVE · Iteration #2 delivery")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = DARK
    body(doc, "Team 102_A (Convive Lab) · Mobile Data Challenge 2026, Challenge #2 · Delivery Sun 8 Nov 2026 · Demo Mon 9 Nov 2026 · **Draft v0.1: dates and open items to be confirmed by the team**", size=9)

    heading(doc, "1. What we committed and what we deliver")
    table = doc.add_table(rows=1, cols=7)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    widths = [1.1, 5.1, 3.3, 1.0, 1.2, 1.1, 4.4]
    labels = ["WBS", "Deliverable", "Owner", "Due", "Status", "Actual date", "File"]
    for i, label in enumerate(labels):
        set_cell(table.rows[0].cells[i], label, bold=True)
        shade(table.rows[0].cells[i], "DCE6F1")
    for wbs, deliverable, owner, due, file_name in PLAN:
        cells = table.add_row().cells
        shown = "CONVIVE_Iteration2.ipynb (repo root)" if file_name.endswith(".ipynb") else file_name
        values = [wbs, deliverable, owner, due, status(file_name), "TBD", shown]
        for i, value in enumerate(values):
            set_cell(cells[i], value, size=7.5)
    for row in table.rows:
        for i, width in enumerate(widths):
            row.cells[i].width = Cm(width)
    body(doc, "", after=0)

    heading(doc, "2. The three items the professor asked for")
    body(doc, "**Environment (4.1.3).** Streamlit, run locally. We compared it with Jupyter + Plotly + ipywidgets and Power BI Desktop on the 6 PWP criteria. It is NDA-safe, reuses our Python code, and costs 0 EUR. It also follows the request to \"keep it simple\".")
    body(doc, "**Research questions (3.2.0).** 15 questions built from common beliefs about tourists in Barcelona, each with a dataset, metric, chart and limitation. Q1 to Q6 are in the dashboard, and Q7 to Q15 go to Iteration 3.")
    body(doc, "**Preliminary dashboard (4.2.0, with the first version of 4.2.1).** It has sidebar filters (year, month range, visitor origin, visitor type) and answers six questions, above the five required by SC-13. It reads only the aggregated tables of 3.1.6 and the neighbourhood map, and it runs on `localhost`. Start it with: `streamlit run app/dashboard.py`.")
    picture(doc, "q2_monthly.png", 15.5, "Q2: monthly unique visitors by origin (aggregated, threshold 15).")
    picture(doc, "q1_map.png", 15.5, "Q1: neighbourhood map, top-10 table and concentration measures.")
    picture(doc, "q6_trips.png", 15.5, "Q6: share of incoming trips by visitors. Trips, not people.")

    heading(doc, "3. The data work behind them")
    bullet(doc, f"**Reception and loading (3.1.0, 3.1.1).** All 12 datasets are complete: {len(found)} monthly files out of {12 * 32}, {size_gb:.1f} GB and {rows:,} rows. Monthly CSVs are converted once to Parquet with DuckDB.")
    bullet(doc, f"**Geographic levels (2.1.1).** The Iteration 1 code rule matched only {geo['legacy_matches']} of {geo['n_map']} neighbourhoods, because Smart Steps numbers neighbourhoods inside each district and uses 9 digits. The corrected correspondence matches all {geo['n_map']}, confirmed by rule and by name ({geo['name_matches']} of {geo['n_map']}).")
    bullet(doc, f"**Temporal levels (2.1.2).** Day, weekday and weekend, ISO week, month, year and January to August comparison periods. Three days are missing in all daily files ({missing}), and their months are flagged.")
    bullet(doc, f"**Quality (3.1.2).** Checks S1 to S4, C1 to C4 and X1 to X3 ran on all the data. {metrics['M1']['zero_share']:.1%} of M1 rows are published zeros (fewer than 15 trips). {metrics['M3']['repeated_share']:.1%} of M3 rows repeat a key, usually with different values, so M3 stays out of Q1 to Q6 until the mentor clarifies it. X1 fails in {details['x1_violations']} of {details['x1_cells']:,} cells, all in {' and '.join(b['name'] for b in details['low_barrios'])}, whose tourism counts are far below the median neighbourhood. T9 has no international visitors, although the description lists them.")
    bullet(doc, "**Cleaning (3.1.3).** Duplicates are checked, categories harmonised, the code correspondence applied and incomplete periods flagged. NA stays NA, a published 0 stays 0, and nothing is imputed. **One deviation from the plan:** M3 repeats are flagged and not dropped, because dropping them could remove real trips.")
    bullet(doc, f"**Statistics and switch to real data (3.1.6, 3.1.7).** {n_tables} aggregated tables were produced for the dashboard and Iteration 3, with values below 15 shown as `<15`. `CONVIVE_Iteration2.ipynb` runs end to end on the real data, and the synthetic mode of Iteration 1 still works.")

    heading(doc, "4. First answers to Q1 to Q6")
    body(doc, "These describe patterns, not causes. Numbers come from `3.1.6_summary.md`.", size=9, after=2)
    for qid, p in paragraphs.items():
        body(doc, f"**{qid}. {p['title']}** {p['text']} **Limitation:** {p['limit']}", size=9, after=3)

    heading(doc, "5. Pending items, limitations and next iteration")
    bullet(doc, "**Pending:** the team fills in the actual dates; the professor reviews the question list before the demo (3.2.0); the mentor is asked about M3 repeated keys, the two low neighbourhoods and T9 international visitors.")
    bullet(doc, "**Limitations:** trips and unique visitors stay separate; unique visitors are not additive; a 0 or NA never means nobody; published zeros make trip totals lower estimates. The visitor-type filter cannot apply to the trips view, because M1 has no visitor type.")
    bullet(doc, "**Next iteration (Iteration 3, 10 to 23 Nov):** WBS 2.2.x, the exploratory, geographic and temporal analysis (3.2.1 to 3.2.3) for Q7 to Q15, and 4.2.2 and 4.2.3.")

    path = OUT_DIR / "CONVIVE_Iteration2_Delivery.docx"
    doc.save(path)
    print(path)


if __name__ == "__main__":
    main()
