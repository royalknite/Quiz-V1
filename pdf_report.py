"""Quiz Report PDF generator.

Generates a quiz report in the exact format:
  • Page 1 : Header banner  +  Leaderboard table
  • Page 2+: QUESTIONS & ANSWERS in a 2-column layout
              (Q text, A/B/C/D options, Explanation)

Hindi / Devanagari is rendered correctly via NotoSansDevanagari + HarfBuzz shaping.
"""

from __future__ import annotations

import math
import os
import re
import random
from datetime import datetime
from typing import Dict, List, Optional

from fpdf import FPDF

FONT_DIR = os.path.join(os.path.dirname(__file__), "assets", "fonts")

FONT_REGULAR      = os.path.join(FONT_DIR, "NotoSans-Regular.ttf")
FONT_BOLD         = os.path.join(FONT_DIR, "NotoSans-Bold.ttf")
FONT_DEVA_REGULAR = os.path.join(FONT_DIR, "NotoSansDevanagari-Regular.ttf")
FONT_DEVA_BOLD    = os.path.join(FONT_DIR, "NotoSansDevanagari-Bold.ttf")

OPTION_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE  = re.compile(r"[ \t]+")

# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W  = 210
PAGE_H  = 297
M_L     = 10          # left margin
M_R     = 10          # right margin
M_TOP   = 10          # top margin
M_BOT   = 12          # bottom margin (footer lives here)
PRINT_W = PAGE_W - M_L - M_R   # 190 mm

# Two-column Q&A layout
COL_GAP    = 5        # gap between columns
COL_W      = (PRINT_W - COL_GAP) // 2    # ≈92 mm each
COL_X      = [M_L, M_L + COL_W + COL_GAP]

# Content vertical bounds for Q&A pages
QA_TOP_Y    = 20      # y where Q&A content starts (after thin header)
QA_BOTTOM_Y = PAGE_H - M_BOT - 3   # ≈282 mm


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub("", str(text))
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"'))
    lines = [_WS_RE.sub(" ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _line_count(text: str, width_mm: float, chars_per_mm: float = 3.6) -> int:
    """Estimate wrapped line count for *text* in a multi_cell of *width_mm*."""
    if not text:
        return 1
    cpp = max(1, int(width_mm * chars_per_mm))
    count = 0
    for para in text.split("\n"):
        count += max(1, math.ceil(len(para) / cpp))
    return count


def _q_height_estimate(q: Dict, col_w: float) -> float:
    """Estimate total vertical mm needed to render one question block."""
    q_text = _strip_html(q.get("question") or "")
    opts   = [_strip_html(o) for o in (q.get("options") or [])]
    exp    = _strip_html(q.get("explanation") or "")

    h  = 2.0                                                 # top padding
    h += 6.5 + (_line_count(q_text, col_w - 9) - 1) * 5.5  # question text
    h += 1.5                                                 # gap
    for opt in opts:
        h += 5.0 + (_line_count(opt, col_w - 2) - 1) * 4.5
    if exp:
        h += 2.0
        h += _line_count(exp, col_w - 4) * 4.5
    h += 5.0                                                 # bottom + divider
    return h


# ── PDF class ─────────────────────────────────────────────────────────────────

class QuizReportPDF(FPDF):
    def __init__(self, quiz_name: str, channel: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.quiz_name = quiz_name
        self.channel   = channel
        self.set_auto_page_break(auto=False)
        self.set_margins(M_L, M_TOP, M_R)

        self.add_font("Noto",     "",  FONT_REGULAR)
        self.add_font("Noto",     "B", FONT_BOLD)
        self.add_font("NotoDeva", "",  FONT_DEVA_REGULAR)
        self.add_font("NotoDeva", "B", FONT_DEVA_BOLD)
        self.set_fallback_fonts(["NotoDeva"])

        try:
            self.set_text_shaping(True)
        except Exception:
            pass

    def header(self):
        pass  # all headers drawn manually

    def footer(self):
        self.set_y(-10)
        self.set_font("Noto", "", 7)
        self.set_text_color(140, 140, 140)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)


# ── Page-1: header banner + leaderboard ───────────────────────────────────────

def _write_page1(pdf: QuizReportPDF,
                 quiz_name: str,
                 channel: str,
                 date_str: str,
                 total_q: int,
                 pos_mark: str,
                 neg_mark: str,
                 leaderboard: List[Dict]) -> None:

    pdf.add_page()

    # ── Top banner ────────────────────────────────────────────────────────
    pdf.set_fill_color(20, 80, 170)
    pdf.rect(0, 0, PAGE_W, 26, style="F")

    pdf.set_xy(M_L, 3)
    pdf.set_font("Noto", "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(PRINT_W, 7, quiz_name, align="L")

    pdf.set_x(M_L)
    pdf.set_font("Noto", "", 8)
    meta = f"{channel}   |   {date_str}   |   {total_q} Questions   |   +{pos_mark} / -{neg_mark}"
    pdf.multi_cell(PRINT_W, 5, meta, align="L")

    pdf.set_text_color(0, 0, 0)

    # ── Leaderboard ───────────────────────────────────────────────────────
    y = 32
    pdf.set_xy(M_L, y)
    pdf.set_font("Noto", "B", 11)
    pdf.set_text_color(20, 80, 170)
    pdf.cell(0, 7, "LEADERBOARD")
    pdf.set_text_color(0, 0, 0)
    y += 9

    if not leaderboard:
        pdf.set_xy(M_L, y)
        pdf.set_font("Noto", "", 10)
        pdf.cell(0, 7, "No participants.")
        return

    # Table header
    col_widths = [12, 70, 18, 14, 18, 26, 22]  # Rank Name Score Wrong Acc% Time (Extra removed)
    headers    = ["Rank", "Participant", "Score", "Wrong", "Acc%", "Time"]
    col_widths = [12, 76, 20, 18, 20, 28]       # adjust to fit 190 mm

    row_h = 7
    pdf.set_xy(M_L, y)
    pdf.set_fill_color(230, 237, 255)
    pdf.set_font("Noto", "B", 8)
    x = M_L
    for i, (hdr, cw) in enumerate(zip(headers, col_widths)):
        pdf.set_xy(x, y)
        pdf.cell(cw, row_h, hdr, border="B", fill=True, align="C")
        x += cw
    y += row_h

    pdf.set_font("Noto", "", 8)
    for rank_i, user in enumerate(leaderboard, start=1):
        if y + row_h > QA_BOTTOM_Y:
            break                                   # leaderboard truncated; rest on next page

        total_att = user.get("correct", 0) + user.get("wrong", 0)
        acc = (user["correct"] / total_att * 100) if total_att else 0
        mins, secs = divmod(int(user.get("total_time", 0)), 60)
        time_str = f"{mins}m {secs}s"

        rank_icon = ""
        if rank_i == 1:   rank_icon = "[1st] "
        elif rank_i == 2: rank_icon = "[2nd] "
        elif rank_i == 3: rank_icon = "[3rd] "

        fill_color = None
        if rank_i == 1:   fill_color = (255, 245, 157)
        elif rank_i == 2: fill_color = (224, 224, 224)
        elif rank_i == 3: fill_color = (255, 224, 178)

        row_data = [
            f"{rank_icon}{rank_i}.",
            user.get("name", "")[:32],
            f"{user.get('score', 0):.0f}",
            str(user.get("wrong", 0)),
            f"{acc:.0f}%",
            time_str,
        ]

        x = M_L
        for j, (val, cw) in enumerate(zip(row_data, col_widths)):
            pdf.set_xy(x, y)
            if fill_color:
                pdf.set_fill_color(*fill_color)
                pdf.cell(cw, row_h, val, border="B", fill=True,
                         align="C" if j != 1 else "L")
                pdf.set_fill_color(255, 255, 255)
            else:
                fill = (rank_i % 2 == 0)
                if fill:
                    pdf.set_fill_color(248, 250, 255)
                pdf.cell(cw, row_h, val, border="B", fill=fill,
                         align="C" if j != 1 else "L")
                pdf.set_fill_color(255, 255, 255)
            x += cw
        y += row_h


# ── Q&A rendering helpers ─────────────────────────────────────────────────────
def _draw_qa_page_header(pdf: QuizReportPDF) -> None:
    """Small top stripe; question cards remain the main focus."""
    pdf.set_fill_color(20, 80, 170)
    pdf.rect(0, 0, PAGE_W, 5, style="F")


def _text_height(pdf: QuizReportPDF, text: str, width: float, line_h: float) -> float:
    """Measure wrapped text height without changing the document."""
    if not text:
        return line_h
    try:
        lines = pdf.multi_cell(width, line_h, text, dry_run=True, output="LINES")
        return max(1, len(lines)) * line_h
    except Exception:
        chars = max(8, int(width * 3.2))
        lines = sum(max(1, math.ceil(len(p) / chars)) for p in text.split("\n"))
        return lines * line_h


def _q_card_height(pdf: QuizReportPDF, q: Dict, card_w: float) -> float:
    """Estimate the complete height of one question card."""
    q_text = _strip_html(q.get("question") or "") or "(no question text)"
    opts = [_strip_html(o) for o in (q.get("options") or [])]
    exp = _strip_html(q.get("explanation") or "")
    inner_w = card_w - 10

    h = 6.5
    h += max(7.0, _text_height(pdf, q_text, inner_w - 23, 5.4))
    h += 2.5
    for opt in opts:
        h += max(7.0, _text_height(pdf, opt or "", inner_w - 16, 5.1)) + 1.5
    if exp:
        h += 3.0
        h += 7.0 + _text_height(pdf, exp, inner_w - 16, 4.5) + 5.0
    h += 5.0
    return h


def _render_question_card(pdf: QuizReportPDF,
                         q: Dict,
                         idx: int,
                         y: float,
                         card_w: float) -> float:
    """Render one full-width question card matching the supplied reference."""
    x = M_L
    inner_x = x + 5
    inner_w = card_w - 10

    q_text = _strip_html(q.get("question") or "") or "(no question text)"
    opts = [_strip_html(o) for o in (q.get("options") or [])]
    exp = _strip_html(q.get("explanation") or "")
    correct_id = q.get("correct_option_id")
    card_h = _q_card_height(pdf, q, card_w)

    # White card + blue left accent.
    pdf.set_fill_color(255, 255, 255)
    try:
        pdf.rounded_rect(x, y, card_w, card_h, 2.5, style="F")
    except Exception:
        pdf.rect(x, y, card_w, card_h, style="F")

    pdf.set_draw_color(30, 86, 190)
    pdf.set_line_width(1.25)
    pdf.line(x + 1.0, y + 2.0, x + 1.0, y + card_h - 2.0)
    pdf.set_line_width(0.2)

    # Blue Q-number badge.
    badge_w, badge_h = 13, 7.5
    pdf.set_fill_color(28, 88, 196)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Noto", "B", 9)
    try:
        pdf.rounded_rect(inner_x, y + 4.0, badge_w, badge_h, 2.0, style="F")
    except Exception:
        pdf.rect(inner_x, y + 4.0, badge_w, badge_h, style="F")
    pdf.set_xy(inner_x, y + 4.2)
    pdf.cell(badge_w, 6.5, f"Q{idx}", align="C")

    # Question text.
    qx = inner_x + badge_w + 3.5
    qw = inner_w - badge_w - 3.5
    pdf.set_xy(qx, y + 3.5)
    pdf.set_font("NotoDeva", "B", 10.2)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(qw, 5.4, q_text)
    cy = max(pdf.get_y(), y + 12.0) + 2.5

    # Options.
    for i, opt in enumerate(opts):
        letter = OPTION_LETTERS[i] if i < len(OPTION_LETTERS) else str(i + 1)
        is_correct = (i == correct_id)
        ox = inner_x + 2
        ow = inner_w - 4
        oh = max(7.0, _text_height(pdf, opt or "", ow - 14, 5.1) + 2.0)

        if is_correct:
            pdf.set_fill_color(239, 252, 244)
            pdf.set_text_color(21, 154, 85)
            try:
                pdf.rounded_rect(ox, cy, ow, oh, 1.6, style="F")
            except Exception:
                pdf.rect(ox, cy, ow, oh, style="F")
            font_style = "B"
        else:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(45, 45, 45)
            font_style = ""

        pdf.set_font("NotoDeva", font_style, 9.3)
        pdf.set_xy(ox + 2, cy + 0.7)
        pdf.cell(10, 5.5, f"{letter})", align="L")
        pdf.set_xy(ox + 12, cy + 0.7)
        pdf.multi_cell(ow - 14, 5.1, opt or "")
        cy += oh + 1.0

    # Yellow explanation box.
    if exp:
        cy += 2.0
        ex = inner_x + 1
        ew = inner_w - 2
        text_x = ex + 5
        text_w = ew - 10
        exp_body_h = _text_height(pdf, exp, text_w, 4.5)
        exp_h = 8.0 + exp_body_h + 5.0

        pdf.set_fill_color(255, 249, 204)
        pdf.set_draw_color(245, 196, 35)
        pdf.set_line_width(0.7)
        try:
            pdf.rounded_rect(ex, cy, ew, exp_h, 2.0, style="DF")
        except Exception:
            pdf.rect(ex, cy, ew, exp_h, style="DF")
        pdf.set_line_width(0.2)

        pdf.set_xy(text_x, cy + 2.0)
        pdf.set_font("NotoDeva", "B", 9.3)
        pdf.set_text_color(116, 76, 18)
        pdf.cell(text_w, 5.0, "Explanation:")
        pdf.set_xy(text_x, pdf.get_y() + 1.0)
        pdf.set_font("NotoDeva", "", 8.6)
        pdf.multi_cell(text_w, 4.5, exp)
        cy = max(cy + exp_h, pdf.get_y())

    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(0, 0, 0)
    return y + card_h


def _write_qa_pages(pdf: QuizReportPDF, questions: List[Dict]) -> None:
    """Write questions as full-width cards, one below another."""
    pdf.add_page()
    _draw_qa_page_header(pdf)

    y = 12.0
    card_w = PRINT_W
    bottom = PAGE_H - M_BOT - 4

    for idx, q in enumerate(questions, start=1):
        try:
            needed = _q_card_height(pdf, q, card_w)
        except Exception:
            needed = 70.0

        if y > 12.0 and y + needed > bottom:
            pdf.add_page()
            _draw_qa_page_header(pdf)
            y = 12.0

        try:
            y = _render_question_card(pdf, q, idx, y, card_w) + 5.0
        except Exception:
            y += 10.0

# ── Public API ────────────────────────────────────────────────────────────────

def generate_mock_test_pdf(
    quiz: Dict,
    output_path: str,
    channel: str = "@AIpha_World",
    leaderboard: Optional[List[Dict]] = None,
    shuffle: bool = False,
) -> str:
    """
    Render *quiz* to a PDF at *output_path*.

    Parameters
    ----------
    quiz        : MongoDB quiz document (must contain 'questions' list)
    output_path : destination file path
    channel     : channel handle shown in header
    leaderboard : list of participant result dicts (optional)
    shuffle     : if True, randomise question order in the PDF

    Returns the output_path.
    """
    quiz_name  = (quiz.get("quiz_name") or "Quiz").strip() or "Quiz"
    questions  = list(quiz.get("questions") or [])

    if not questions:
        raise ValueError("Quiz has no questions to export.")

    # Shuffle question order if requested
    if shuffle:
        random.shuffle(questions)

    neg = quiz.get("negative_marking") or quiz.get("negative_marks") or 0
    try:
        neg = float(neg)
    except (TypeError, ValueError):
        neg = 0.0

    pos_str = "1"
    neg_str = f"{neg:g}" if neg else "0"
    date_str = datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    total_q = len(questions)

    pdf = QuizReportPDF(quiz_name=quiz_name, channel=channel)

    # Page 1: header + leaderboard
    _write_page1(
        pdf,
        quiz_name=quiz_name,
        channel=channel,
        date_str=date_str,
        total_q=total_q,
        pos_mark=pos_str,
        neg_mark=neg_str,
        leaderboard=leaderboard or [],
    )

    # Pages 2+: Q&A
    _write_qa_pages(pdf, questions)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    pdf.output(output_path)
    return output_path
