import os
import uuid
import html
import threading
from datetime import datetime

from flask import Flask, jsonify, send_file, request
from weasyprint import HTML


app = Flask(__name__)

JOBS = {}


def esc(value):
    return html.escape(str(value or ""), quote=True)


def nl(value):
    return esc(value).replace("\n", "<br>")


def get_correct_ids(value):
    if isinstance(value, list):
        result = []
        for x in value:
            try:
                result.append(int(x))
            except Exception:
                pass
        return result

    try:
        return [int(value)]
    except Exception:
        return [0]


def option_letter(index):
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if 0 <= index < len(letters):
        return letters[index]
    return str(index + 1)


def render_question_content(text):
    """Render normal question text plus a pipe-delimited matching table."""
    text = str(text or "")
    lines = text.splitlines()
    table_rows = []
    normal_lines = []
    for line in lines:
        stripped = line.strip()
        if "|" in stripped:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and all(c and set(c.replace(":", "").strip()) <= {"-"} for c in cells):
                continue
            if len(cells) >= 2:
                table_rows.append(cells)
                continue
        normal_lines.append(line)

    parts = []
    normal = "\n".join(normal_lines).strip()
    if normal:
        parts.append(f'<div class="question-normal">{nl(normal)}</div>')

    if len(table_rows) >= 2:
        cols = max(len(r) for r in table_rows)
        rows_html = []
        for ri, row in enumerate(table_rows):
            row = row + [""] * (cols - len(row))
            tag = "th" if ri == 0 else "td"
            rows_html.append("<tr>" + "".join(f"<{tag}>{nl(cell)}</{tag}>" for cell in row) + "</tr>")
        parts.append(
            '<div class="matching-table-wrap">'
            '<table class="matching-table"><tbody>'
            + "".join(rows_html)
            + "</tbody></table></div>"
        )
    return "".join(parts) if parts else nl(text)


def build_pdf_html(data):

    questions = data.get("questions_json", [])
    solution_display = "inline"

    exam_title = data.get("exam_title", "Mock Test")
    mock_number = data.get("mock_number", "01")
    generated_date = datetime.now().strftime("%d %B %Y")

    question_html = ""

    for index, q in enumerate(questions, start=1):

        question_text = q.get("question", "")
        options = q.get("options", [])

        correct_ids = get_correct_ids(
            q.get("correct_option_id", 0)
        )

        explanation = q.get("explanation", "")
        reply_text = q.get("reply_text", "")

        options_html = ""

        for opt_index, option in enumerate(options):

            letter = option_letter(opt_index)
            is_correct = opt_index in correct_ids

            cls = "option correct" if is_correct else "option"

            options_html += f"""
            <div class="{cls}">
                <span class="option-letter">{letter})</span>
                <span>{nl(option)}</span>
            </div>
            """

        solution_html = ""

        if solution_display == "inline":

            solution_html = f"""
            <div class="solution-box">
                <div class="solution-title">
                    Explanation:
                </div>
                <div class="solution-text">
                    {nl(explanation)}
                </div>
            </div>
            """

        reference_html = ""

        if reply_text:

            reference_html = f"""
            <div class="reference-box">
                <b>Reference:</b>
                {nl(reply_text)}
            </div>
            """

        question_html += f"""
        <div class="question-card">

            <div class="question-header-line">
                <span class="question-number">Q{index}</span>
                <div class="question-text">
                    {render_question_content(question_text)}
                </div>
            </div>

            <div class="options">
                {options_html}
            </div>

            {reference_html}
            {solution_html}

        </div>
        """

    return f"""
<!DOCTYPE html>
<html lang="hi">

<head>
<meta charset="UTF-8">
<style>

@font-face {{
    font-family: "NotoHindi";
    src: url("fonts/NotoSansDevanagari-Regular.ttf");
    font-weight: 400;
}}

@font-face {{
    font-family: "NotoHindi";
    src: url("fonts/NotoSansDevanagari-Bold.ttf");
    font-weight: 700;
}}

@page {{
    size: A4;
    margin: 20mm 13mm 18mm 13mm;

    @top-left {{
        content: "QUICK STUDY GROUP";
        font-family: "NotoHindi", sans-serif;
        font-size: 10pt;
        font-weight: 800;
        color: #8d1f26;
        padding-bottom: 4px;
        border-bottom: 1.2px solid #9b1c1c;
    }}

    @top-right {{
        content: "GENERATED: {esc(generated_date)}";
        font-family: "NotoHindi", sans-serif;
        font-size: 7.5pt;
        color: #777;
        padding-bottom: 4px;
        border-bottom: 1.2px solid #9b1c1c;
    }}

    @bottom-left {{
        content: "QUICK STUDY GROUP";
        font-family: "NotoHindi", sans-serif;
        font-size: 8pt;
        color: #888;
        padding-top: 4px;
        border-top: 1px solid #ddd;
    }}

    @bottom-right {{
        content: "पृष्ठ " counter(page) " / " counter(pages);
        font-family: "NotoHindi", sans-serif;
        font-size: 8pt;
        color: #777;
        padding-top: 4px;
        border-top: 1px solid #ddd;
    }}
}}

@page :first {{
    margin-top: 12mm;
    @top-left {{ content: none; border: none; }}
    @top-center {{ content: none; border: none; }}
    @top-right {{ content: none; border: none; }}
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #FFFFFF;
    font-family: "NotoHindi", "Noto Sans Devanagari", sans-serif;
    color: #161616;
    font-size: 9pt;
    line-height: 1.4;
}}

.main-title {{
    border: 1.5px solid #1D4ED8;
    border-radius: 15px;
    background: #EFF6FF;
    padding: 12px;
    text-align: center;
    margin-bottom: 12px;
}}

.main-brand {{
    font-size: 18pt;
    font-weight: 900;
    color: #1E3A8A;
    margin-bottom: 3px;
}}

.exam-title {{
    font-size: 12pt;
    font-weight: 800;
    color: #222;
}}

.mock-number {{
    font-size: 9.5pt;
    font-weight: 700;
    color: #8d1f26;
    margin-top: 2px;
}}

.test-meta {{
    display: flex;
    justify-content: center;
    gap: 16px;
    font-size: 7.5pt;
    color: #666;
    margin-top: 5px;
}}

.questions-title {{
    font-size: 11pt;
    font-weight: 900;
    color: #8d1f26;
    border-bottom: 1px solid #d8b7b7;
    padding-bottom: 3px;
    margin-bottom: 8px;
}}

.questions-container {{
    column-count: 2;
    column-gap: 10mm;
    column-fill: auto;
}}

/* Smooth rounded question card. The explanation remains inside this same card. */
.question-card {{
    display: block;
    break-inside: avoid;
    page-break-inside: avoid;
    margin-bottom: 10px;
    padding: 9px 10px 10px 10px;
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-left: 4px solid #1d4ed8;
    border-radius: 11px;
    overflow: hidden;
}}

.question-header-line {{
    display: block;
}}

.question-number {{
    display: inline-block;
    background: #1d4ed8;
    color: #ffffff;
    font-weight: 900;
    font-size: 8.5pt;
    padding: 2px 6px 2px 6px;
    border-radius: 4px;
    margin-right: 4px;
    margin-bottom: 4px;
}}

.question-text {{
    display: inline;
    font-weight: 800;
    font-size: 8.8pt;
}}

.options {{
    margin-top: 3px;
    margin-left: 0;
}}

/* Options are tight: no unnecessary vertical gap between A/B/C/D. */
.option {{
    display: block;
    break-inside: avoid;
    page-break-inside: avoid;
    padding: 2px 4px;
    margin: 0;
    font-size: 8.3pt;
    color: #333;
}}

.option.correct {{
    background: #F0FDF4;
    color: #159A55;
    border-radius: 4px;
    font-weight: 700;
}}

.option.correct .option-letter,
.option.correct span {{
    color: #159A55;
}}

.option-letter {{
    font-weight: 900;
    color: #4b5563;
    margin-right: 3px;
}}

.matching-table-wrap {{
    margin: 5px 0;
    width: 100%;
    break-inside: avoid;
    page-break-inside: avoid;
}}

.matching-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 7.8pt;
    line-height: 1.2;
}}

.matching-table th, .matching-table td {{
    border: 1px solid #777;
    padding: 3px 4px;
    vertical-align: middle;
    text-align: left;
    overflow-wrap: anywhere;
}}

.matching-table th:nth-child(1) {{
    background: #FECACA;
    font-weight: 800;
}}

.matching-table th:nth-child(2) {{
    background: #BFDBFE;
    font-weight: 800;
}}

.matching-table td {{
    background: #FFFFFF;
}}

/* Explanation is a child of question-card: one integrated rounded block. */
.solution-box {{
    display: block;
    width: 100%;
    margin-top: 6px;
    padding: 7px 9px;
    background: #FFF9CC;
    border: 1px solid #F5C423;
    border-radius: 7px;
    break-inside: avoid;
    page-break-inside: avoid;
}}

/* No separate yellow strip / no border-left accent here. */
.solution-title {{
    font-weight: 900;
    color: #713f12;
    font-size: 8.2pt;
    margin-bottom: 2px;
}}

.solution-text {{
    font-size: 7.6pt;
    color: #4f4a35;
    line-height: 1.3;
}}

.reference-box {{
    display: block;
    margin-top: 5px;
    padding: 5px 7px;
    background: #f8fafc;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    break-inside: avoid;
    page-break-inside: avoid;
    font-size: 7.6pt;
}}

.watermark {{
    position: fixed;
    top: 47%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-30deg);
    font-size: 38pt;
    font-weight: 900;
    color: #9b1c1c;
    opacity: .035;
    z-index: -1;
    white-space: nowrap;
}}

</style>
</head>

<body>

<div class="watermark">
    QUICK STUDY GROUP
</div>

<div class="main-title">
    <div class="main-brand">QUICK STUDY GROUP</div>
    <div class="exam-title">{esc(exam_title)}</div>
    <div class="mock-number">Mock Test - {esc(mock_number)}</div>
    <div class="test-meta">
        <span>Questions: {len(questions)}</span>
    </div>
</div>

<div class="questions-title">Questions & Solutions</div>

<div class="questions-container">
    {question_html}
</div>

</body>
</html>
"""


def generate_pdf(job_id, data):
    try:
        JOBS[job_id] = {"status": "processing", "error": None}
        pdf_path = f"/tmp/{job_id}.pdf"
        
        html_content = build_pdf_html(data)
        
        if not html_content:
            raise ValueError("HTML content is empty")

        HTML(
            string=html_content,
            base_url=os.path.dirname(os.path.abspath(__file__))
        ).write_pdf(pdf_path)

        JOBS[job_id] = {
            "status": "done",
            "error": None,
            "file": pdf_path,
        }

    except Exception as exc:
        JOBS[job_id] = {
            "status": "error",
            "error": str(exc),
        }


@app.route("/")
def home():
    return jsonify({"service": "Quick Study Group PDF API", "status": "online", "version": "2.2"})


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get("questions_json"):
        return jsonify({"error": "questions_json is required"}), 400

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued", "error": None}
    
    thread = threading.Thread(target=generate_pdf, args=(job_id, data), daemon=True)
    thread.start()

    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "progress_url": f"/api/progress/{job_id}",
        "download_url": f"/api/download/{job_id}",
    })


@app.route("/api/progress/<job_id>")
def progress(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"status": "error", "error": "Job not found"}), 404
    return jsonify({"status": job.get("status"), "error": job.get("error")})


@app.route("/api/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "PDF not ready or not found"}), 404

    pdf_path = job.get("file")
    if not pdf_path or not os.path.exists(pdf_path):
        return jsonify({"error": "PDF file not found"}), 404

    return send_file(pdf_path, mimetype="application/pdf", as_attachment=False, download_name="MockTest_With_Solutions.pdf")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
