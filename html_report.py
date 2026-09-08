"""Separate HTML result report generator for the V1 quiz bot."""
import html
import json
import os
import time


def _safe(value):
    return html.escape("" if value is None else str(value))


def _answer_for_question(participant, index):
    answers = participant.get("answers") or {}
    value = answers.get(f"q{index}")
    if isinstance(value, dict):
        return value.get("option")
    if isinstance(value, int):
        return value
    return None


async def send_quiz_result_html(results_file, quiz_data, chat_id, context, protect_content=False):
    """Send a normal quiz result HTML report; this is not the Compare Results report."""
    if not results_file or not os.path.exists(results_file):
        return False

    with open(results_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    participants = results.get("participants") or []
    participant = next((p for p in participants if int(p.get("user_id", 0)) == int(chat_id)), None)
    if participant is None and participants:
        participant = participants[0]
    participant = participant or {}

    questions = quiz_data.get("questions") or []
    correct = int(participant.get("correct", 0) or 0)
    wrong = int(participant.get("wrong", 0) or 0)
    total = len(questions)
    unanswered = max(0, total - correct - wrong)
    score = participant.get("score", 0)
    try:
        score_text = f"{float(score):.2f}"
    except (TypeError, ValueError):
        score_text = _safe(score)
    percentage = (correct / total * 100) if total else 0
    total_time = int(participant.get("total_time", 0) or 0)
    minutes, seconds = divmod(total_time, 60)

    cards = []
    for i, q in enumerate(questions):
        options = q.get("options") or []
        correct_id = q.get("correct_option_id")
        selected = _answer_for_question(participant, i)
        rows = []
        for oid, option in enumerate(options):
            cls = " correct" if oid == correct_id else (" wrong" if selected is not None and oid == selected else "")
            letter = chr(65 + oid)
            rows.append(f'<div class="option{cls}"><b>{letter}.</b> {_safe(option)}</div>')
        explanation = q.get("explanation") or "No explanation available."
        cards.append(
            f'<section class="question"><div class="qhead">Q{i + 1}</div>'
            f'<h3>{_safe(q.get("question", ""))}</h3>'
            f'<div>{"".join(rows)}</div>'
            f'<div class="explanation"><b>Explanation:</b> {_safe(explanation)}</div></section>'
        )

    quiz_name = _safe(quiz_data.get("quiz_name", results.get("quiz_name", "Quiz")))
    document = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quiz Result</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#1f2937;font-family:Arial,Segoe UI,sans-serif}
.wrap{max-width:900px;margin:auto;padding:18px}.header{background:linear-gradient(135deg,#4361ee,#3f37c9);color:#fff;border-radius:16px;padding:24px;margin-bottom:16px}
.header h1{margin:0 0 6px;font-size:28px}.header p{margin:0;opacity:.9}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.stat{background:#fff;border-radius:12px;padding:15px;text-align:center;box-shadow:0 2px 8px #00000010}.stat b{display:block;font-size:22px;margin-top:5px}
.question{background:#fff;border-radius:14px;padding:18px;margin:12px 0;box-shadow:0 2px 8px #0000000d;border-left:4px solid #4361ee}
.qhead{display:inline-block;background:#4361ee;color:#fff;border-radius:8px;padding:4px 9px;font-weight:700}.question h3{font-size:18px;line-height:1.5;margin:12px 0}
.option{padding:10px 12px;border:1px solid #e5e7eb;border-radius:8px;margin:7px 0;background:#fff}.option.correct{background:#f0fdf4;border-color:#86efac;color:#159a55;font-weight:700}
.option.wrong{background:#fef2f2;border-color:#fca5a5;color:#dc2626;font-weight:700}.explanation{margin-top:12px;background:#fffbea;border:1px solid #f6c945;border-left:4px solid #f59e0b;border-radius:8px;padding:12px;line-height:1.5}
.footer{text-align:center;color:#6b7280;padding:18px}@media(max-width:650px){.wrap{padding:10px}.header h1{font-size:23px}.summary{grid-template-columns:repeat(2,1fr)}.question{padding:14px}}
</style></head><body><main class="wrap">
<header class="header"><h1>Quiz Result</h1><p>__QUIZ_NAME__</p></header>
<div class="summary"><div class="stat">Correct<b>__CORRECT__</b></div><div class="stat">Wrong<b>__WRONG__</b></div>
<div class="stat">Not Answered<b>__UNANSWERED__</b></div><div class="stat">Score<b>__SCORE__</b></div></div>
<div class="summary"><div class="stat">Percentage<b>__PERCENTAGE__%</b></div><div class="stat">Time<b>__TIME__</b></div>
<div class="stat">Total Questions<b>__TOTAL__</b></div><div class="stat">Negative Marks<b>__NEGATIVE__</b></div></div>
__CARDS__<div class="footer">Quiz Result Report</div></main></body></html>"""
    document = document.replace("__QUIZ_NAME__", quiz_name).replace("__CORRECT__", str(correct)).replace("__WRONG__", str(wrong))
    document = document.replace("__UNANSWERED__", str(unanswered)).replace("__SCORE__", score_text)
    document = document.replace("__PERCENTAGE__", f"{percentage:.1f}").replace("__TIME__", f"{minutes}m {seconds}s")
    document = document.replace("__TOTAL__", str(total)).replace("__NEGATIVE__", _safe(results.get("negative_marking", 0)))
    document = document.replace("__CARDS__", "".join(cards))

    os.makedirs("reports", exist_ok=True)
    quiz_id = quiz_data.get("question_set_id") or results.get("quiz_id") or "QUIZ"
    filename = f"reports/{chat_id}_{quiz_id}_{int(time.time())}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(document)

    try:
        with open(filename, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id, document=f, filename=f"QuizReport_{quiz_id}.html",
                caption=f"📄 {quiz_data.get('quiz_name', 'Quiz')}\n\n<b>HTML Quiz Report</b>",
                parse_mode="HTML", protect_content=bool(protect_content)
            )
    finally:
        try:
            os.remove(filename)
        except OSError:
            pass
    return True
