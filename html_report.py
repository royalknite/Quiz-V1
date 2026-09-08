"""HTML quiz result report helper.

Keeps HTML report generation separate from bot.py, similar to pdf_report.py.
The existing HTML generator in c.py is reused unchanged.
"""

import json
import os
import time


async def send_quiz_result_html(results_file, quiz_data, chat_id, context, protect_content=False):
    try:
        from c import generate_analysis_html
    except ImportError:
        return False

    if not results_file or not os.path.exists(results_file):
        return False

    try:
        with open(results_file, "r", encoding="utf-8") as f:
            quiz_results = json.load(f)

        html_content = await generate_analysis_html(quiz_results, quiz_data)
        if not html_content:
            return False

        os.makedirs("reports", exist_ok=True)
        quiz_id = quiz_data.get("question_set_id") or quiz_data.get("quiz_id") or "QUIZ"
        timestamp = int(time.time())
        html_file = f"reports/{chat_id}_{quiz_id}_{timestamp}.html"

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        try:
            with open(html_file, "rb") as f:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=f"QuizReport_{quiz_id}.html",
                    caption=f"📄 {quiz_data.get('quiz_name', 'Quiz')}\n\n<b>HTML Quiz Report</b>",
                    parse_mode="HTML",
                    protect_content=bool(protect_content),
                )
        finally:
            try:
                os.remove(html_file)
            except OSError:
                pass

        return True
    except Exception:
        raise
