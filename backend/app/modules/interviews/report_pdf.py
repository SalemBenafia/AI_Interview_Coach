"""
app/modules/interviews/report_pdf.py
=======================================
Real PDF generation for the downloadable interview report
(roles.txt -> User -> Feedback & Reports -> "Download report").
Uses fpdf2 -- a pure-Python PDF library, no system dependencies (unlike
wkhtmltopdf/weasyprint), so it works in any container without extra
native packages.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fpdf import FPDF

BRAND_GREEN = (0, 255, 159)   # matches the frontend's neon accent (#00ff9f)
DARK_BG = (10, 15, 10)
MUTED = (110, 120, 110)


class _ReportPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*BRAND_GREEN)
        self.cell(0, 10, "AI Interview Coach -- Performance Report", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BRAND_GREEN)
        self.line(10, 20, 200, 20)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _section_title(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 20, 20)
    pdf.ln(2)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Helvetica", "", 11)


def _bullet_list(pdf: FPDF, items: list[str]) -> None:
    for item in items:
        pdf.set_x(14)
        pdf.multi_cell(0, 6, f"-  {item}", new_x="LMARGIN", new_y="NEXT")
    if not items:
        pdf.set_x(14)
        pdf.multi_cell(0, 6, "(none recorded)", new_x="LMARGIN", new_y="NEXT")


def build_report_pdf(
    *,
    candidate_name: str,
    role_name: str,
    mode: str,
    difficulty: str,
    generated_at: datetime,
    overall_score: Optional[float],
    communication_score: Optional[float],
    technical_score: Optional[float],
    behavioral_score: Optional[float],
    confidence_score: Optional[float],
    summary: str,
    strengths: list[str],
    weaknesses: list[str],
    suggestions: list[str],
    recommended_practice: list[str],
    example_better_answers: list[dict],
    sentiment_summary: Optional[str] = None,
) -> bytes:
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, f"Candidate: {candidate_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Role: {role_name}    Mode: {mode.title()}    Difficulty: {difficulty.title()}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}", new_x="LMARGIN", new_y="NEXT")

    _section_title(pdf, "Scores")
    score_rows = [
        ("Overall", overall_score),
        ("Communication", communication_score),
        ("Technical Depth", technical_score),
        ("Behavioral / STAR", behavioral_score),
        ("Confidence", confidence_score),
    ]
    for label, value in score_rows:
        display = f"{value:.0f} / 100" if value is not None else "n/a"
        pdf.cell(60, 7, label)
        pdf.cell(0, 7, display, new_x="LMARGIN", new_y="NEXT")

    _section_title(pdf, "Summary")
    pdf.multi_cell(0, 6, summary or "No summary available.", new_x="LMARGIN", new_y="NEXT")

    _section_title(pdf, "Strengths")
    _bullet_list(pdf, strengths)

    _section_title(pdf, "Areas to Improve")
    _bullet_list(pdf, weaknesses)

    _section_title(pdf, "Suggestions")
    _bullet_list(pdf, suggestions)

    if sentiment_summary:
        _section_title(pdf, "Emotional Tone")
        pdf.multi_cell(0, 6, f"Detected tone across your spoken answers: {sentiment_summary}.", new_x="LMARGIN", new_y="NEXT")

    if example_better_answers:
        _section_title(pdf, "Example Improved Answers")
        for ex in example_better_answers:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, f"Q: {ex.get('question', '')}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, f"Your answer: {ex.get('your_answer', '')}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*BRAND_GREEN)
            pdf.multi_cell(0, 6, f"Stronger answer: {ex.get('better_answer', '')}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(60, 60, 60)
            pdf.ln(2)

    _section_title(pdf, "Recommended Next Practice")
    _bullet_list(pdf, recommended_practice)

    return bytes(pdf.output())
