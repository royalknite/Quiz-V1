"""
Quiz-V1 optional Advanced Question Card plugin.

Purpose:
- Keep the existing Quiz-V1 logic untouched.
- Upgrade only the question pre-message for structured questions.
- Direct/simple MCQs continue through the original Quiz-V1 path.
- Matching, Assertion-Reason, statement and table/list questions can be shown
  as a clean full question card before the Telegram poll, similar to the
  Advance Quiz Bot style.

Installation:
1. Copy this file beside bot.py.
2. Add ONE line near the bottom of bot.py, after all function definitions and
   before `def main():`:
       import rich_quiz; rich_quiz.install(globals())

No existing function body needs to be edited.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_PLUGIN_MARKER = "_RICH_QUIZ_INSTALLED_V1"

# Structured-question cues. These are intentionally conservative so ordinary
# direct MCQs keep the existing behaviour.
_STRUCTURED_PATTERNS = [
    re.compile(r"(?:कथन\s*\(A\)|Assertion\s*\(A\))\s*:", re.I),
    re.compile(r"(?:कारण\s*\(R\)|Reason\s*\(R\))\s*:", re.I),
    re.compile(r"\b(?:I|II|III|IV)\.\s+"),
    re.compile(r"(?:सूची\s*[-–—]?\s*I|सूची\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:List\s*[-–—]?\s*I|List\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:मिलान|सुमेलित|Match\s+the\s+following)", re.I),
    re.compile(r"→"),
    re.compile(r"\[\s*Poll\s*:", re.I),
    re.compile(r"(?:Options?|विकल्प)\s*:", re.I),
]

# Table-like text: multiple rows containing a vertical separator, or the
# common Hindi/English list-column headings.
_TABLE_PATTERNS = [
    re.compile(r"^\s*\|.+\|\s*$", re.M),
    re.compile(r"(?:व्यक्ति|वर्ष|व्यक्ति|घटना|सूची\s*-?\s*I|सूची\s*-?\s*II).{0,80}(?:वर्ष|सूची\s*-?\s*II)", re.I | re.S),
]


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[\s*Poll\s*:\s*\[\d+\s*/\s*\d+\s*\]\s*\]", "", text, flags=re.I)
    text = re.sub(r"^\s*\[\d+\s*/\s*\d+\]\s*", "", text)
    return text.strip()


def _normalise_statements(text: str) -> str:
    # Put Roman-numbered statements on separate lines.
    return re.sub(
        r"([?।.!])\s+((?:I{1,3}|IV)\.\s+)",
        r"\1\n\2",
        text,
    )


def _normalise_matching(text: str) -> str:
    lines: List[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        # If several arrow pairs were accidentally placed on one line, split
        # before the next numbered/lettered item.
        if line.count("→") > 1:
            parts = re.split(r"\s+(?=(?:[A-D]|\d+)[.)]\s*\S+.*?→)", line)
            lines.extend(p.strip() for p in parts if p.strip())
        else:
            lines.append(line)
    return "\n".join(lines)


def _looks_structured(question: str, options: Optional[List[str]] = None) -> bool:
    q = question or ""
    if any(p.search(q) for p in _STRUCTURED_PATTERNS):
        return True
    if any(p.search(q) for p in _TABLE_PATTERNS):
        return True
    # Some imported matching questions have the table headings in options.
    if options:
        joined = "\n".join(str(x) for x in options)
        if any(p.search(joined) for p in _TABLE_PATTERNS):
            return True
        if "→" in joined:
            return True
    return False


def _format_card(question: str, question_number: int, total_questions: int) -> str:
    body = _clean(question)
    body = _normalise_statements(body)
    body = _normalise_matching(body)

    # Remove duplicate standalone poll instruction markers when they are
    # already embedded in the source question.
    body = re.sub(r"^\s*\[\s*Poll\s*:\s*.*?$", "", body, flags=re.I | re.M).strip()

    return f"Q{question_number}/{total_questions}\n\n{body}".strip()


async def _rich_preamble(
    original,
    context: Any,
    chat_id: int,
    question: str,
    options: Optional[List[str]] = None,
    question_number: int = 0,
    total_questions: int = 0,
    explanation: Optional[str] = None,
    correct_option_id: Optional[int] = None,
) -> bool:
    """Wrapper: preserve the original sender first, then add only missing
    structured-card support."""
    # Let Quiz-V1's own tested formatting win first.
    try:
        result = await original(
            context, chat_id, question, options, question_number, total_questions,
            explanation, correct_option_id
        )
        if result:
            return True
    except Exception:
        # Never break the existing quiz flow because of the optional plugin.
        pass

    if not _looks_structured(question, options):
        return False

    try:
        # Use the bot's existing retry-safe sender. No custom Bot API method is
        # required, so the plugin works with normal python-telegram-bot.
        sender = context.bot.send_message
        text = _format_card(question, question_number, total_questions)
        await sender(chat_id=chat_id, text=text)
        return True
    except Exception:
        # The caller will continue with the normal poll path.
        return False


def install(namespace: Dict[str, Any]) -> bool:
    """Install the optional question-card wrapper into bot.py's globals.

    This changes only the two global references used by the existing quiz
    sender; no existing function bodies are modified.
    """
    if namespace.get(_PLUGIN_MARKER):
        return True

    original = namespace.get("send_question_preamble")
    if not callable(original):
        return False

    async def wrapped(
        context: Any,
        chat_id: int,
        question: str,
        options=None,
        question_number: int = 0,
        total_questions: int = 0,
        explanation: str = None,
        correct_option_id: int = None,
    ) -> bool:
        return await _rich_preamble(
            original, context, chat_id, question, options,
            question_number, total_questions, explanation, correct_option_id,
        )

    namespace["send_question_preamble"] = wrapped
    # Existing call sites use this backwards-compatible alias.
    namespace["send_full_question_text"] = wrapped
    namespace[_PLUGIN_MARKER] = True
    return True
