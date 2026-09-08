"""Optional visual question-card add-on for Quiz-V1.

Adds a Telegram photo card before the existing poll for structured questions.
Direct MCQs and all existing quiz/timer/scoring functions are left untouched.
Activation from bot.py:
    import rich_quiz; rich_quiz.install(globals())
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

_MARKER = "_RICH_VISUAL_TABLE_INSTALLED_V1"

_STRUCTURED = [
    re.compile(r"(?:कथन\s*\(A\)|Assertion\s*\(A\))\s*:", re.I),
    re.compile(r"(?:कारण\s*\(R\)|Reason\s*\(R\))\s*:", re.I),
    re.compile(r"(?:^|\n)\s*(?:I|II|III|IV)\.\s+"),
    re.compile(r"(?:सूची\s*[-–—]?\s*I|सूची\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:List\s*[-–—]?\s*I|List\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:मिलान|सुमेलित|Match\s+the\s+following)", re.I),
    re.compile(r"→"),
    re.compile(r"\[\s*Poll\s*:", re.I),
]
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")


def _font_path(bold: bool = False, devanagari: bool = False) -> str:
    base = "assets/fonts/"
    if devanagari:
        return base + ("NotoSansDevanagari-Bold.ttf" if bold else "NotoSansDevanagari-Regular.ttf")
    return base + ("NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf")


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    import os
    candidates = [_font_path(bold, True), _font_path(bold, False)]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[\s*Poll\s*:\s*\[\d+\s*/\s*\d+\]\s*\]", "", text, flags=re.I)
    text = re.sub(r"^\s*\[\d+\s*/\s*\d+\]\s*", "", text)
    return text.strip()


def _is_table_start(lines: List[str], i: int) -> bool:
    return i + 1 < len(lines) and bool(_TABLE_ROW.match(lines[i])) and bool(_TABLE_SEP.match(lines[i + 1]))


def _split_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [x.strip() for x in s.split("|")]


def _extract_table(lines: List[str], i: int) -> Tuple[List[List[str]], int]:
    rows: List[List[str]] = []
    rows.append(_split_row(lines[i]))
    i += 2  # skip separator
    while i < len(lines) and _TABLE_ROW.match(lines[i]):
        rows.append(_split_row(lines[i]))
        i += 1
    cols = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (cols - len(r)) for r in rows]
    return rows, i


def _prepare(question: str) -> Tuple[List[str], Optional[List[List[str]]]]:
    text = _clean(question)
    # The actual poll already contains A-D, so do not duplicate choices on the card.
    text = re.sub(r"\n\s*A\)\s+.*?(?=\n\s*Ex\s*:|$)", "", text, flags=re.S)
    text = re.sub(r"\n\s*Ex\s*:.*$", "", text, flags=re.S | re.I)
    lines = [x.strip() for x in text.splitlines() if x.strip()]

    prose: List[str] = []
    table: Optional[List[List[str]]] = None
    i = 0
    while i < len(lines):
        if table is None and _is_table_start(lines, i):
            table, i = _extract_table(lines, i)
            continue
        line = re.sub(r"\s+((?:I|II|III|IV)\.\s+)", r"\n\1", lines[i])
        prose.extend(x.strip() for x in line.splitlines() if x.strip())
        i += 1
    return prose, table


def _is_structured(question: str, options: Optional[List[str]]) -> bool:
    q = question or ""
    if any(p.search(q) for p in _STRUCTURED) or _TABLE_ROW.search(q):
        return True
    if options:
        joined = "\n".join(map(str, options))
        return "→" in joined or bool(_TABLE_ROW.search(joined))
    return False


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    words = list(text) if any("\u0900" <= c <= "\u097f" for c in text) else text.split()
    lines: List[str] = []
    cur = ""
    for token in words:
        candidate = cur + token if (not cur or any("\u0900" <= c <= "\u097f" for c in text)) else (cur + " " + token)
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_w or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = token
    if cur:
        lines.append(cur)
    return lines


def _table_dimensions(draw: ImageDraw.ImageDraw, rows: List[List[str]], font: ImageFont.FreeTypeFont, max_w: int) -> Tuple[List[int], List[List[List[str]]]]:
    cols = len(rows[0])
    wrapped: List[List[List[str]]] = []
    natural = [70] * cols
    for row in rows:
        wr: List[List[str]] = []
        for c in range(cols):
            cell = row[c]
            lines = _wrap(draw, cell, font, max(100, max_w // cols - 24))
            wr.append(lines)
            natural[c] = max(natural[c], max(draw.textbbox((0,0), ln, font=font)[2] for ln in lines) + 24)
        wrapped.append(wr)
    total = sum(natural)
    if total > max_w:
        scale = max_w / total
        natural = [max(90, int(w * scale)) for w in natural]
    return natural, wrapped


def _render_card(question: str, n: int, total: int) -> io.BytesIO:
    prose, table = _prepare(question)
    W = 1080
    margin = 54
    inner_w = W - margin * 2
    title_font = _load_font(42, True)
    q_font = _load_font(36, False)
    table_head = _load_font(30, True)
    table_font = _load_font(29, False)

    # First pass on a temporary canvas for accurate wrapping/height.
    dummy = Image.new("RGB", (W, 100), "white")
    d = ImageDraw.Draw(dummy)
    body_lines: List[str] = []
    for p in prose:
        body_lines.extend(_wrap(d, p, q_font, inner_w - 20))

    table_cols: Optional[List[int]] = None
    table_wrapped = None
    if table:
        table_cols, table_wrapped = _table_dimensions(d, table, table_font, inner_w - 20)

    h = 44 + 58 + 28
    h += len(body_lines) * 52 + (18 if body_lines else 0)
    if table_wrapped and table_cols:
        for r, row in enumerate(table_wrapped):
            line_heights = max((len(c) for c in row), default=1)
            h += 50 + line_heights * 40
        h += 22
    h += 34

    img = Image.new("RGB", (W, max(220, h)), "white")
    d = ImageDraw.Draw(img)
    # Rounded card with subtle outline.
    d.rounded_rectangle((8, 8, W-8, h-8), radius=34, fill="white", outline=(215, 215, 215), width=3)

    y = 42
    d.text((margin, y), f"Q{n}/{total}", font=title_font, fill=(30,30,30))
    y += 68

    for line in body_lines:
        d.text((margin, y), line, font=q_font, fill=(25,25,25))
        y += 52
    if body_lines:
        y += 12

    if table and table_cols and table_wrapped:
        x0 = margin
        # header/rows, with light grey fill only in header
        row_heights: List[int] = []
        for r in table_wrapped:
            row_heights.append(50 + max(len(c) for c in r) * 40)
        for ri, (row, rh) in enumerate(zip(table_wrapped, row_heights)):
            x = x0
            fill = (246, 246, 246) if ri == 0 else (255, 255, 255)
            d.rectangle((x, y, x0 + sum(table_cols), y + rh), fill=fill, outline=(205,205,205), width=2)
            for ci, cell_lines in enumerate(row):
                cw = table_cols[ci]
                d.rectangle((x, y, x+cw, y+rh), outline=(215,215,215), width=2)
                f = table_head if ri == 0 else table_font
                line_y = y + 14
                for ln in cell_lines:
                    d.text((x+14, line_y), ln, font=f, fill=(25,25,25))
                    line_y += 40
                x += cw
            y += rh
        y += 22

    # Recreate exact height crop after drawing.
    img = img.crop((0, 0, W, min(h, max(y + 24, 220))))
    bio = io.BytesIO()
    bio.name = "question_card.png"
    img.save(bio, format="PNG", optimize=True)
    bio.seek(0)
    return bio


async def _wrapped_preamble(original, context: Any, chat_id: int, question: str,
                            options=None, question_number: int = 0,
                            total_questions: int = 0, explanation: str = None,
                            correct_option_id: int = None) -> bool:
    if _is_structured(question, options):
        try:
            card = _render_card(question, question_number, total_questions)
            await context.bot.send_photo(chat_id=chat_id, photo=card)
            return True
        except Exception:
            # Fall back to the bot's original renderer rather than breaking the quiz.
            pass
    try:
        result = await original(context, chat_id, question, options, question_number,
                                total_questions, explanation, correct_option_id)
        return bool(result)
    except Exception:
        return False


def install(namespace: Dict[str, Any]) -> bool:
    """Install the visual card wrapper without editing existing function bodies."""
    if namespace.get(_MARKER):
        return True
    original = namespace.get("send_question_preamble")
    if not callable(original):
        return False

    async def wrapped(context, chat_id, question, options=None,
                      question_number=0, total_questions=0,
                      explanation=None, correct_option_id=None):
        return await _wrapped_preamble(original, context, chat_id, question, options,
                                       question_number, total_questions, explanation,
                                       correct_option_id)

    namespace["send_question_preamble"] = wrapped
    namespace["send_full_question_text"] = wrapped
    namespace[_MARKER] = True
    return True
