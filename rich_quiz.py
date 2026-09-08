"""Optional Rich/Box question-card add-on for Quiz-V1.

Install beside bot.py and activate with:
    import rich_quiz; rich_quiz.install(globals())

Only structured questions get the extra card. Direct MCQs keep the existing path.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

_MARKER = "_RICH_QUIZ_INSTALLED_V2"

STRUCTURED = [
    re.compile(r"(?:कथन\s*\(A\)|Assertion\s*\(A\))\s*:", re.I),
    re.compile(r"(?:कारण\s*\(R\)|Reason\s*\(R\))\s*:", re.I),
    re.compile(r"(?:I|II|III|IV)\.\s+"),
    re.compile(r"(?:सूची\s*[-–—]?\s*I|सूची\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:List\s*[-–—]?\s*I|List\s*[-–—]?\s*II)", re.I),
    re.compile(r"(?:मिलान|सुमेलित|Match\s+the\s+following)", re.I),
    re.compile(r"→"),
    re.compile(r"\[\s*Poll\s*:", re.I),
]
TABLE = re.compile(r"^\s*\|.+\|\s*$", re.M)


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\[\s*Poll\s*:\s*\[\d+\s*/\s*\d+\s*\]\s*\]", "", text, flags=re.I)
    text = re.sub(r"^\s*\[\d+\s*/\s*\d+\]\s*", "", text)
    return text.strip()


def _normalise(text: str) -> str:
    text = re.sub(r"([?।.!])\s+((?:I|II|III|IV)\.\s+)", r"\1\n\2", text)
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Markdown separator row adds no useful information in the card.
        if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?", line):
            continue
        out.append(line)
    return "\n".join(out)


def _is_structured(question: str, options: Optional[List[str]]) -> bool:
    q = question or ""
    if any(p.search(q) for p in STRUCTURED) or TABLE.search(q):
        return True
    if options:
        joined = "\n".join(map(str, options))
        if "→" in joined or TABLE.search(joined):
            return True
    return False


def _box_card(question: str, n: int, total: int) -> str:
    body = _normalise(_clean(question))
    # Keep the card focused on the question/table. Poll choices remain in the poll.
    body = re.sub(r"\n\s*A\)\s+.*?(?=\n\s*Ex\s*:|$)", "", body, flags=re.S)
    body = re.sub(r"\n\s*Ex\s*:.*$", "", body, flags=re.S | re.I)
    if not body:
        body = _clean(question)
    lines = body.splitlines()
    width = min(58, max([len(x) for x in lines] + [18]))
    top = "╭" + "─" * (width + 2) + "╮"
    bottom = "╰" + "─" * (width + 2) + "╯"
    header = f"│ Q{n}/{total}".ljust(width + 2) + "│"
    rendered = [top, header, "│" + " " * (width + 2) + "│"]
    for line in lines:
        # Preserve table/column text; clip only extremely long single lines.
        if len(line) > width:
            chunks = [line[i:i+width] for i in range(0, len(line), width)]
        else:
            chunks = [line]
        for chunk in chunks:
            rendered.append("│ " + chunk.ljust(width) + " │")
    rendered.append(bottom)
    return "\n".join(rendered)


async def _wrapped_preamble(original, context: Any, chat_id: int, question: str,
                            options=None, question_number: int = 0,
                            total_questions: int = 0, explanation: str = None,
                            correct_option_id: int = None) -> bool:
    # Structured questions: use the new boxed card FIRST, so the old plain card
    # is not emitted. This changes presentation only; poll/timer logic is untouched.
    if _is_structured(question, options):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=_box_card(question, question_number, total_questions),
            )
            return True
        except Exception:
            # Fall back to the original renderer if the optional card fails.
            pass

    # Direct/simple MCQs, and any failed rich card, use the original implementation.
    try:
        result = await original(
            context, chat_id, question, options, question_number,
            total_questions, explanation, correct_option_id
        )
        return bool(result)
    except Exception:
        return False


def install(namespace: Dict[str, Any]) -> bool:
    """Activate the add-on without changing existing function bodies."""
    if namespace.get(_MARKER):
        return True
    original = namespace.get("send_question_preamble")
    if not callable(original):
        return False

    async def wrapped(context, chat_id, question, options=None,
                      question_number=0, total_questions=0,
                      explanation=None, correct_option_id=None):
        return await _wrapped_preamble(
            original, context, chat_id, question, options,
            question_number, total_questions, explanation, correct_option_id
        )

    namespace["send_question_preamble"] = wrapped
    namespace["send_full_question_text"] = wrapped
    namespace[_MARKER] = True
    return True
