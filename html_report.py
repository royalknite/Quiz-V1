"""Interactive HTML quiz report generator.

Kept separate from the original c.py so the existing quiz functions remain untouched.
"""
import os
import re
import json
import random
import uuid
from unidecode import unidecode

async def generate_quiz_html(quiz, chat_id, context, ParseMode, type):
    """Premium Quiz HTML Generator - Mobile + Desktop CBT Platform"""
    
    def je(t):
        """JS escape"""
        if not t: return ""
        t = str(t)
        return t.replace('\\','\\\\').replace('"','\\"').replace("'","\\'").replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
    
    # Quiz metadata
    qn = re.sub(r"[^a-zA-Z0-9_-]", "", unidecode(quiz["quiz_name"]).replace(" ", "_"))[:100] + ".html"
    mm = len(quiz["questions"])
    nm = quiz.get("negative_marks", 0.25)
    
    # ── Section support ──────────────────────────────────────────────
    sections = quiz.get("sections", [])
    has_sections = bool(sections)

    if has_sections:
        # Build section JS array: [{name, start(0-idx), end(0-idx), timer(sec)}]
        sec_js_parts = []
        total_sec_time = 0
        for s in sections:
            sname = je(s["name"])
            sr = s["question_range"]          # 1-indexed tuple (start, end)
            s_start = int(sr[0]) - 1          # convert to 0-indexed
            s_end   = int(sr[1]) - 1
            num_q_in_section = s_end - s_start + 1
            s_timer = int(s.get("timer", 60)) * num_q_in_section
            total_sec_time += s_timer
            sec_js_parts.append(
                f'{{name:"{sname}",start:{s_start},end:{s_end},timer:{s_timer}}}'
            )
        sec_js = "[" + ",".join(sec_js_parts) + "]"
        dt = total_sec_time                   # total quiz time in seconds
    else:
        sec_js = "[]"
        timer_per_q = quiz.get("timer", 60)
        if timer_per_q is None:
            timer_per_q = 60
        dt = timer_per_q * mm
    # ────────────────────────────────────────────────────────────────

    # Build questions JS
    qjs = []
    for i, q in enumerate(quiz["questions"]):
        opts = q["options"].copy()
        co = opts[q["correct_option_id"]]
        random.shuffle(opts)
        qjs.append(f'''{{id:{i},txt:"{je(q["question"])}",ref:"{je(q.get("reply_text",""))}",opts:{json.dumps(opts)},ci:{opts.index(co)},exp:"{je(q.get("explanation","No explanation"))}"}}''')
    
    # Desktop CBT Styles
    dsk_css = """
    @media (min-width: 1024px) {
        body { overflow: auto !important; }
        
        #quizContainer {
            display: grid !important;
            grid-template-columns: 1fr 320px;
            grid-template-rows: auto 1fr auto;
            gap: 0;
            height: 100vh;
            overflow: hidden;
        }
        
        .quiz-header {
            grid-column: 1 / -1;
            position: static;
            padding: 20px 32px;
            border-bottom: 3px solid var(--border);
        }
        
        .header-top {
            max-width: none;
            margin-bottom: 16px;
        }
        
        .quiz-title-text { max-width: 400px; }
        
        .timer-display {
            padding: 10px 20px;
            font-size: 18px;
        }
        
        /* Main content area - scrollable */
        .question-section {
            position: static !important;
            grid-column: 1;
            grid-row: 2;
            overflow-y: auto;
            padding: 32px;
            background: var(--bg-light);
            top: auto !important;
            bottom: auto !important;
        }
        
        .question-card {
            max-width: 900px;
            padding: 32px;
            margin: 0 auto 24px;
        }
        
        .question-text {
            font-size: 18px;
            margin-bottom: 24px;
        }
        
        .option-btn {
            padding: 18px 20px;
            font-size: 16px;
        }
        
        .option-indicator {
            min-width: 32px;
            height: 32px;
            font-size: 14px;
        }
        
        /* Desktop Question Navigator - Right Panel */
        .question-nav-panel {
            position: static !important;
            grid-column: 2;
            grid-row: 2;
            transform: none !important;
            max-height: none;
            height: 100%;
            border-radius: 0;
            border-left: 3px solid var(--border);
            box-shadow: none;
            padding: 24px;
            overflow-y: auto;
            background: var(--bg-white);
        }
        
        .question-nav-panel.open { transform: none !important; }
        
        .nav-panel-header {
            position: sticky;
            top: 0;
            background: var(--bg-white);
            z-index: 10;
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        
        .nav-panel-title {
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .nav-close-btn { display: none; }
        
        .nav-legend {
            position: sticky;
            top: 60px;
            background: var(--bg-white);
            z-index: 9;
            padding: 16px;
            margin: -16px -16px 20px;
            border-radius: 12px;
            background: var(--bg-light);
        }
        
        .question-grid {
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }
        
        .question-nav-item {
            aspect-ratio: 1;
            font-size: 16px;
            border-radius: 12px;
        }
        
        .question-nav-toggle { display: none; }
        
        /* Footer Navigation - Sticky */
        .nav-controls {
            position: static;
            grid-column: 1;
            grid-row: 3;
            padding: 20px 32px;
            border-top: 3px solid var(--border);
            max-width: none;
            display: flex;
            justify-content: center;
            gap: 16px;
        }
        
        .nav-btn {
            min-width: 160px;
            padding: 16px 24px;
            font-size: 16px;
        }
        
        /* Results Desktop Layout */
        #resultsContainer {
            padding: 40px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .results-header {
            padding: 60px 40px;
            margin-bottom: 32px;
        }
        
        .results-icon { font-size: 100px; }
        .results-title { font-size: 36px; }
        .results-score { font-size: 64px; }
        .results-percentage { font-size: 24px; }
        
        .stats-grid {
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 32px;
            max-width: none;
        }
        
        .stat-card { padding: 32px; }
        .stat-icon { width: 54px; height: 54px; font-size: 24px; }
        .stat-value { font-size: 40px; }
        .stat-label { font-size: 14px; }
        
        .action-buttons {
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            max-width: 800px;
        }
        
        .action-btn { padding: 20px; font-size: 17px; }
        
        /* Mode Selection Desktop */
        .mode-container {
            max-width: 600px;
            padding: 50px 40px;
        }
        
        .mode-header-icon {
            width: 80px;
            height: 80px;
            font-size: 40px;
        }
        
        .mode-header h2 { font-size: 28px; }
        .mode-header p { font-size: 15px; }
        
        .mode-cards { gap: 20px; }
        
        .mode-card {
            padding: 24px;
            border-radius: 18px;
        }
        
        .mode-icon {
            width: 60px;
            height: 60px;
            font-size: 28px;
            margin-right: 20px;
        }
        
        .mode-info h3 { font-size: 19px; }
        .mode-info p { font-size: 14px; }
        
        .timer-input { padding: 16px 18px; font-size: 16px; }
        .start-btn { padding: 18px; font-size: 17px; }
    }
    
    /* Ultra-wide Desktop */
    @media (min-width: 1440px) {
        #quizContainer {
            grid-template-columns: 1fr 380px;
        }
        
        .question-section { padding: 40px 60px; }
        .question-card { max-width: 1000px; padding: 40px; }
        .question-nav-panel { padding: 32px; }
        .question-grid { grid-template-columns: repeat(5, 1fr); }
        .nav-controls { padding: 24px 60px; }
    }
    """
    
    # Main HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{quiz['quiz_name']}</title>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}}
:root{{--primary:#667eea;--primary-dark:#5568d3;--secondary:#764ba2;--success:#48bb78;--danger:#f5576c;--warning:#fbbf24;--info:#4facfe;--bg-light:#f7fafc;--bg-white:#fff;--text-dark:#1a202c;--text-light:#718096;--border:#e2e8f0}}
[data-theme="dark"]{{--bg-light:#1a202c;--bg-white:#2d3748;--text-dark:#f7fafc;--text-light:#cbd5e0;--border:#4a5568}}
body{{font-family:'Poppins',-apple-system,BlinkMacSystemFont,sans-serif;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);min-height:100vh;overflow:hidden;user-select:none;-webkit-user-select:none;transition:background .3s}}
.scrollable::-webkit-scrollbar{{width:6px}}
.scrollable::-webkit-scrollbar-track{{background:transparent}}
.scrollable::-webkit-scrollbar-thumb{{background:var(--primary);border-radius:10px}}
.protected-content{{white-space:pre-wrap!important;word-wrap:break-word!important;word-break:break-word!important;overflow-wrap:break-word!important;line-height:1.7;user-select:none}}
.option-btn .protected-content,.option-text.protected-content{{display:block;min-width:0;max-width:100%}}
#modeSelection{{position:fixed;top:0;left:0;width:100%;height:100%;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);display:flex;align-items:center;justify-content:center;z-index:9999;padding:20px;overflow-y:auto}}
.mode-container{{background:#fff;border-radius:24px;padding:40px 30px;max-width:500px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.3);animation:ms .5s cubic-bezier(.34,1.56,.64,1)}}
@keyframes ms{{from{{opacity:0;transform:translateY(40px) scale(.95)}}to{{opacity:1;transform:translateY(0) scale(1)}}}}
.mode-header{{text-align:center;margin-bottom:32px}}
.mode-header-icon{{width:70px;height:70px;margin:0 auto 16px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:36px;color:#fff;box-shadow:0 8px 24px rgba(102,126,234,.3)}}
.mode-header h2{{font-size:24px;font-weight:700;color:#1a202c;margin-bottom:8px}}
.mode-header p{{font-size:14px;color:#718096;font-weight:400}}
.mode-cards{{display:grid;gap:16px;margin-bottom:24px}}
.mode-card{{background:#f7fafc;border:2px solid #e2e8f0;border-radius:16px;padding:20px;cursor:pointer;transition:all .3s;position:relative}}
.mode-card:hover{{transform:translateY(-3px);box-shadow:0 12px 28px rgba(102,126,234,.15);border-color:#cbd5e0}}
.mode-card.selected{{border-color:#667eea;background:#fff;box-shadow:0 8px 24px rgba(102,126,234,.2);transform:translateY(-2px)}}
.mode-card-header{{display:flex;align-items:center}}
.mode-icon{{width:54px;height:54px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:24px;margin-right:16px;flex-shrink:0}}
.exam-mode .mode-icon{{background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);color:#fff}}
.practice-mode .mode-icon{{background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%);color:#fff}}
.mode-info h3{{font-size:17px;font-weight:700;color:#1a202c;margin-bottom:4px}}
.mode-info p{{font-size:13px;color:#718096;line-height:1.4}}
.timer-config{{margin-bottom:24px}}
.timer-config label{{display:block;font-size:14px;font-weight:600;color:#1a202c;margin-bottom:10px}}
.timer-config label i{{margin-right:6px;color:#667eea}}
.timer-input{{width:100%;padding:14px 16px;border:2px solid #e2e8f0;border-radius:12px;font-size:15px;font-weight:500;transition:all .3s;background:#fff;font-family:'Poppins',sans-serif;color:#1a202c}}
.timer-input::placeholder{{color:#a0aec0}}
.timer-input:focus{{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.1)}}
.start-btn{{width:100%;padding:16px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;border:none;border-radius:14px;font-size:16px;font-weight:700;cursor:pointer;transition:all .3s;display:flex;align-items:center;justify-content:center;gap:10px;box-shadow:0 8px 20px rgba(102,126,234,.35)}}
.start-btn:hover:not(:disabled){{transform:translateY(-2px);box-shadow:0 12px 28px rgba(102,126,234,.45)}}
.start-btn:active:not(:disabled){{transform:translateY(0)}}
.start-btn:disabled{{opacity:.5;cursor:not-allowed;background:#cbd5e0;box-shadow:none}}
#quizContainer{{display:none;position:fixed;top:0;left:0;width:100%;height:100vh;background:var(--bg-light);overflow:hidden}}
.quiz-header{{position:fixed;top:0;left:0;right:0;background:var(--bg-white);box-shadow:0 2px 15px rgba(0,0,0,.08);z-index:100;padding:16px 20px}}
.header-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;gap:10px}}
.quiz-title{{font-size:15px;font-weight:700;color:var(--text-dark);display:flex;align-items:center;gap:8px;flex:1;min-width:0}}
.quiz-title-text{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:150px}}
.mode-badge{{font-size:10px;padding:4px 10px;border-radius:20px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}}
.mode-badge.exam{{background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);color:#fff}}
.mode-badge.practice{{background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%);color:#fff}}
.header-actions{{display:flex;gap:8px;align-items:center}}
.theme-toggle{{width:36px;height:36px;background:var(--bg-light);border:none;border-radius:10px;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:16px;color:var(--text-dark);transition:all .3s}}
.theme-toggle:hover{{transform:scale(1.1)}}
.timer-display{{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:700;color:var(--primary);padding:8px 14px;background:linear-gradient(135deg,rgba(102,126,234,.15) 0%,rgba(118,75,162,.15) 100%);border-radius:12px;white-space:nowrap}}
.timer-display.warning{{color:var(--danger);background:linear-gradient(135deg,rgba(245,87,108,.15) 0%,rgba(240,147,251,.15) 100%);animation:pulse 1s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.7}}}}
.header-progress{{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--text-light);margin-bottom:8px}}
.progress-bar-container{{height:6px;background:var(--border);border-radius:10px;overflow:hidden}}
.progress-bar{{height:100%;background:linear-gradient(90deg,var(--primary) 0%,var(--secondary) 100%);transition:width .3s;border-radius:10px}}
.section-badge{{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:#fff;background:linear-gradient(135deg,#f093fb 0%,#f5576c 100%);padding:4px 12px;border-radius:20px;margin-bottom:10px}}
.question-section{{position:fixed;top:140px;left:0;right:0;bottom:92px;overflow-y:auto;overflow-x:hidden;padding:10px;-webkit-overflow-scrolling:touch}}
.question-section.scrollable{{scrollbar-width:thin;scrollbar-color:var(--primary) transparent}}
.question-card{{background:var(--bg-white);border-radius:14px;padding:14px;box-shadow:0 2px 10px rgba(0,0,0,.05);max-width:800px;margin:0 auto}}
.question-number{{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:var(--primary);background:linear-gradient(135deg,rgba(102,126,234,.15) 0%,rgba(118,75,162,.15) 100%);padding:6px 14px;border-radius:20px;margin-bottom:16px}}
.question-reference{{background:linear-gradient(135deg,rgba(79,172,254,.15) 0%,rgba(0,242,254,.15) 100%);border-left:4px solid var(--info);padding:14px 16px;border-radius:10px;margin-bottom:16px;font-size:14px;color:var(--text-dark);line-height:1.7;white-space:pre-wrap!important;word-wrap:break-word!important;word-break:break-word!important;overflow-wrap:break-word!important}}
.question-text{{font-size:15px;font-weight:600;color:var(--text-dark);line-height:1.5;margin-bottom:12px;white-space:pre-wrap!important;word-wrap:break-word!important;word-break:break-word!important;overflow-wrap:break-word!important}}
.options-container{{display:grid;gap:12px}}
.option-btn{{width:100%;padding:10px 12px;background:var(--bg-light);border:2px solid var(--border);border-radius:10px;text-align:left;font-size:14px;color:var(--text-dark);cursor:pointer;transition:all .2s;display:flex;align-items:flex-start;gap:9px;line-height:1.45;user-select:none}}
.option-btn:active{{transform:scale(.98)}}
.option-indicator{{min-width:28px;height:28px;border-radius:50%;background:var(--bg-white);border:2px solid var(--border);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;transition:all .3s}}
.option-text{{flex:1;padding-top:3px;white-space:pre-wrap!important;word-wrap:break-word!important;word-break:break-word!important;overflow-wrap:break-word!important;min-width:0}}
.option-btn:hover:not(.disabled){{border-color:var(--primary);transform:translateX(4px)}}
.option-btn.selected{{background:linear-gradient(135deg,rgba(102,126,234,.15) 0%,rgba(118,75,162,.15) 100%);border-color:var(--primary)}}
.option-btn.selected .option-indicator{{background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#fff;border-color:transparent}}
.option-btn.correct{{background:linear-gradient(135deg,rgba(72,187,120,.15) 0%,rgba(72,187,120,.15) 100%);border-color:var(--success)}}
.option-btn.correct .option-indicator{{background:var(--success);color:#fff;border-color:transparent}}
.option-btn.incorrect{{background:linear-gradient(135deg,rgba(245,87,108,.15) 0%,rgba(245,87,108,.15) 100%);border-color:var(--danger)}}
.option-btn.incorrect .option-indicator{{background:var(--danger);color:#fff;border-color:transparent}}
.option-btn.disabled{{pointer-events:none;opacity:.6}}
.explanation-box{{display:none;background:linear-gradient(135deg,rgba(254,245,231,.5) 0%,rgba(251,191,36,.2) 100%);border-left:4px solid var(--warning);border-radius:12px;padding:16px;margin-top:20px;animation:sd .3s ease-out}}
@keyframes sd{{from{{opacity:0;max-height:0;padding:0}}to{{opacity:1;max-height:500px;padding:16px}}}}
.explanation-header{{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:700;color:#92400e;margin-bottom:10px}}
.explanation-text{{font-size:14px;color:#78350f;line-height:1.7;white-space:pre-wrap!important;word-wrap:break-word!important;word-break:break-word!important;overflow-wrap:break-word!important}}
[data-theme="dark"] .explanation-text{{color:#fbbf24}}
.nav-controls{{position:fixed;bottom:0;left:0;right:0;background:var(--bg-white);padding:7px 10px;box-shadow:0 -2px 12px rgba(0,0,0,.08);display:grid;grid-template-columns:1fr 1fr;gap:7px;z-index:90}}
.nav-btn{{width:100%;padding:9px 6px;border:none;border-radius:9px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;display:flex;align-items:center;justify-content:center;gap:5px;min-height:38px}}
.nav-btn.primary{{background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#fff}}
.nav-btn.secondary{{background:var(--bg-light);color:var(--text-dark);border:2px solid var(--border)}}
.nav-btn:active{{transform:scale(.96)}}
.nav-btn:disabled{{opacity:.5;cursor:not-allowed;transform:none}}
.question-nav-toggle{{position:fixed;bottom:104px;right:18px;width:56px;height:56px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;border:none;border-radius:50%;font-size:22px;cursor:pointer;box-shadow:0 8px 20px rgba(102,126,234,.4);z-index:85;transition:all .2s}}
.question-nav-toggle:active{{transform:scale(.95)}}

/* Mobile Question Navigator - right side drawer */
.question-nav-panel{{position:fixed;top:0;right:0;bottom:0;left:auto;width:min(84vw,570px);max-width:570px;background:#182b40;color:#fff;border-radius:0;box-shadow:-12px 0 35px rgba(0,0,0,.35);z-index:1001;display:flex;flex-direction:column;overflow:hidden;transform:translateX(105%);transition:transform .25s ease;padding:18px 14px 14px}}
.question-nav-panel.open{{transform:translateX(0)}}
.nav-panel-header{{display:flex;justify-content:space-between;align-items:center;flex:0 0 auto;margin-bottom:14px;padding:4px 2px 14px;border-bottom:1px solid rgba(255,255,255,.12)}}
.nav-panel-title{{font-size:19px;font-weight:700;color:#fff;display:flex;align-items:center;gap:8px;margin:0}}
.nav-panel-title i{{color:#8bd1ff}}
.nav-close-btn{{width:40px;height:40px;background:transparent;border:none;border-radius:10px;font-size:26px;cursor:pointer;color:#fff;display:flex;align-items:center;justify-content:center}}
.nav-close-btn:active{{background:rgba(255,255,255,.1)}}
.nav-legend{{display:grid;grid-template-columns:1fr;gap:8px;margin:0 0 14px;padding:0;flex:0 0 auto;font-size:14px;color:#fff}}
.legend-item{{display:flex;align-items:center;gap:10px;color:#f3f6fa;background:#20364d;border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:9px 12px;min-height:40px}}
.legend-box{{width:22px;height:22px;min-width:22px;border-radius:50%}}
.legend-box.answered{{background:#16c47a}}
.legend-box.marked{{background:#ffbd17}}
.legend-box.unanswered{{background:#438fe8}}
.question-grid{{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px;overflow-y:auto;overflow-x:hidden;align-content:start;padding:2px 0 12px;flex:1 1 auto;scrollbar-width:thin}}
.question-nav-item{{aspect-ratio:1;min-width:0;border:1px solid rgba(255,255,255,.05);border-radius:9px;background:#3a4658;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;cursor:pointer;transition:all .15s;box-sizing:border-box}}
.question-nav-item:active{{transform:scale(.94)}}
.question-nav-item.current{{border:3px solid #fff;background:#3a4658;color:#fff;box-shadow:0 0 0 2px #ffbd17 inset}}
.question-nav-item.answered{{background:#16c47a;color:#fff;border-color:#16c47a}}
.question-nav-item.marked{{background:#ffbd17;color:#162235;border-color:#ffbd17}}
.question-nav-item.correct{{background:#16c47a;color:#fff;border-color:#16c47a}}
.question-nav-item.incorrect{{background:#e74c5b;color:#fff;border-color:#e74c5b}}
.nav-section-label{{grid-column:1/-1;font-size:10px;font-weight:700;color:#9eafc3;text-transform:uppercase;letter-spacing:.5px;padding:7px 2px 3px;border-top:1px solid rgba(255,255,255,.12);margin-top:2px}}
.nav-submit-btn{{flex:0 0 auto;width:100%;margin-top:8px;padding:14px 16px;border:none;border-radius:13px;background:#b7c5dc;color:#17283b;font-size:16px;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;min-height:54px}}
.nav-submit-btn:active{{transform:scale(.985)}}
#resultsContainer{{display:none;position:fixed;top:0;left:0;width:100%;height:100vh;background:var(--bg-light);overflow-y:auto;overflow-x:hidden;padding:20px;z-index:1000}}
#resultsContainer.scrollable{{scrollbar-width:thin;scrollbar-color:var(--primary) transparent}}
.results-header{{text-align:center;padding:32px 20px 28px;background:transparent;border-radius:0;margin-bottom:18px;box-shadow:none}}
.results-main-title{{font-size:34px;font-weight:700;color:#2b4f87;line-height:1.2;margin:0 0 14px}}
.results-subtitle{{font-size:17px;color:#718096;line-height:1.45;margin:0 auto 24px;max-width:700px}}
.results-score{{display:flex;align-items:center;justify-content:center;min-height:150px;padding:24px 20px;border-radius:28px;background:#dff2ff;color:#2182b4;font-size:52px;font-weight:800;line-height:1.15;margin:0 auto 24px;max-width:1000px}}
.results-score-label{{display:block}}
.results-score-value{{display:block}}
.results-percentage{{display:none}}
.results-icon{{display:none}}
.stats-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:0 auto 24px;max-width:1000px}}
.stat-card{{background:#fff;padding:28px 20px;border-radius:22px;box-shadow:0 3px 18px rgba(0,0,0,.035);text-align:center}}
.stat-card.total{{background:#f4f7fb}}
.stat-card.correct-card{{background:#e5f8ef}}
.stat-card.incorrect-card{{background:#fff0f1}}
.stat-card.unanswered-card{{background:#fff8dd}}
.stat-icon{{display:none}}
.stat-value{{font-size:42px;font-weight:700;color:var(--text-dark);margin-bottom:4px}}
.stat-label{{font-size:18px;color:var(--text-light);font-weight:500}}
.stat-card.correct-card .stat-value,.stat-card.correct-card .stat-label{{color:#2b9562}}
.stat-card.incorrect-card .stat-value,.stat-card.incorrect-card .stat-label{{color:#c64f5d}}
.stat-card.unanswered-card .stat-value,.stat-card.unanswered-card .stat-label{{color:#a98508}}
.results-filters{{display:flex;flex-wrap:wrap;gap:14px;margin:0 auto 28px;max-width:1000px}}
.result-filter{{border:1px solid #d9e0e9;background:#fff;color:#1a202c;border-radius:28px;padding:14px 24px;font-size:17px;font-weight:600;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,.02)}}
.result-filter.active{{background:#182536;color:#fff;border-color:#182536}}
.result-filter:active{{transform:scale(.98)}}
.review-list{{max-width:1000px;margin:0 auto;padding-bottom:30px}}
.review-card{{background:#fff;border:1px solid #dce2ea;border-radius:24px;padding:28px 32px;margin-bottom:22px;box-shadow:0 2px 10px rgba(0,0,0,.025)}}
.review-question-number{{font-size:28px;font-weight:600;color:#2b4f87;margin-bottom:30px}}
.review-question-text{{font-size:20px;font-weight:600;color:#18212f;line-height:1.55;white-space:pre-wrap;word-break:break-word;margin-bottom:22px}}
.review-answer-box{{border-radius:18px;padding:16px 20px;margin:12px 0;font-size:18px;line-height:1.5;white-space:pre-wrap;word-break:break-word}}
.review-your-answer{{background:#eef2f7;color:#657386}}
.review-your-answer.wrong{{background:#fff0f1;color:#b94452}}
.review-correct-answer{{background:#e7f8ef;color:#247d57}}
.review-explanation{{background:#fff8dd;border-left:6px solid #f2c315;color:#6d5b20;border-radius:16px;padding:18px 20px;margin-top:14px;font-size:18px;line-height:1.6;white-space:pre-wrap;word-break:break-word}}
.review-hidden{{display:none!important}}
.action-buttons{{display:none}}
.results-icon{{font-size:80px;margin-bottom:20px}}
.results-title{{font-size:28px;font-weight:700;color:var(--text-dark);margin-bottom:10px}}
.results-score{{font-size:52px;font-weight:800;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:10px}}
.results-percentage{{font-size:20px;color:var(--text-light);font-weight:600}}
.stats-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:20px;max-width:800px;margin-left:auto;margin-right:auto}}
.stat-card{{background:var(--bg-white);padding:24px;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.06)}}
.stat-icon{{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px;margin-bottom:12px}}
.stat-icon.correct{{background:linear-gradient(135deg,var(--success) 0%,#38a169 100%);color:#fff}}
.stat-icon.incorrect{{background:linear-gradient(135deg,var(--danger) 0%,#e53e3e 100%);color:#fff}}
.stat-icon.unattempted{{background:linear-gradient(135deg,#a0aec0 0%,#718096 100%);color:#fff}}
.stat-icon.negative{{background:linear-gradient(135deg,#ed8936 0%,#dd6b20 100%);color:#fff}}
.stat-value{{font-size:32px;font-weight:700;color:var(--text-dark);margin-bottom:4px}}
.stat-label{{font-size:13px;color:var(--text-light);font-weight:500}}
.action-buttons{{display:grid;gap:12px;max-width:800px;margin:0 auto}}
.action-btn{{width:100%;padding:18px;border:none;border-radius:12px;font-size:16px;font-weight:600;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:10px;transition:all .3s}}
.action-btn.primary{{background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);color:#fff}}
.action-btn.secondary{{background:var(--bg-white);color:var(--text-dark);border:2px solid var(--border)}}
.action-btn:hover{{transform:translateY(-2px)}}
{dsk_css}
</style>
</head>
<body>
<div id="modeSelection">
<div class="mode-container">
<div class="mode-header">
<div class="mode-header-icon"><i class="fas fa-graduation-cap"></i></div>
<h2>{quiz['quiz_name']}</h2>
<p>Choose your preferred test mode</p>
</div>
<div class="mode-cards">
<div class="mode-card exam-mode" data-mode="exam">
<div class="mode-card-header">
<div class="mode-icon"><i class="fas fa-file-alt"></i></div>
<div class="mode-info">
<h3>Exam Mode</h3>
<p>Complete all questions, results shown after submission</p>
</div>
</div>
</div>
<div class="mode-card practice-mode" data-mode="practice">
<div class="mode-card-header">
<div class="mode-icon"><i class="fas fa-book-open"></i></div>
<div class="mode-info">
<h3>Practice Mode</h3>
<p>Instant feedback with detailed explanations</p>
</div>
</div>
</div>
</div>
<div class="timer-config">
<label for="ct"><i class="fas fa-clock"></i> Custom Timer (minutes)</label>
<input type="number" id="ct" class="timer-input" placeholder="Default: {int(dt/60)} minutes" min="1" max="300"/>
</div>
<button class="start-btn" id="sb" disabled><i class="fas fa-play-circle"></i><span>Start Quiz</span></button>
</div>
</div>
<div id="quizContainer">
<div class="quiz-header">
<div class="header-top">
<div class="quiz-title">
<i class="fas fa-clipboard-list"></i>
<span class="quiz-title-text" title="{quiz['quiz_name']}">{quiz['quiz_name']}</span>
<span class="mode-badge" id="mb"></span>
</div>
<div class="header-actions">
<button class="theme-toggle" id="tt" title="Toggle Dark Mode"><i class="fas fa-moon"></i></button>
<div class="timer-display" id="td"><i class="fas fa-clock"></i><span id="tt2">00:00</span></div>
</div>
</div>
<div class="header-progress">
<span id="pt">Question 1 of {mm}</span>
<span id="at">Attempted: 0/{mm}</span>
</div>
<div class="progress-bar-container"><div class="progress-bar" id="pb"></div></div>
</div>
<div class="question-section scrollable" id="qs"></div>
<div class="nav-controls">
<button class="nav-btn secondary" id="pv"><i class="fas fa-chevron-left"></i>Previous</button>
<button class="nav-btn primary" id="mk"><i class="fas fa-bookmark"></i>Mark for Review</button>
<button class="nav-btn secondary" id="cr"><i class="fas fa-eraser"></i>Clear Response</button>
<button class="nav-btn primary" id="nx">Save &amp; Next <i class="fas fa-chevron-right"></i></button>
<button class="nav-btn primary" id="sm" style="display:none"><i class="fas fa-paper-plane"></i>Submit Test</button>
</div>
<button class="question-nav-toggle" id="nt"><i class="fas fa-th"></i></button>
<div class="question-nav-panel" id="np">
<div class="nav-panel-header">
<h3 class="nav-panel-title"><i class="fas fa-map-marked-alt"></i> Question Navigator</h3>
<button class="nav-close-btn" id="nc"><i class="fas fa-times"></i></button>
</div>
<div class="nav-legend">
<div class="legend-item"><div class="legend-box answered"></div><span>Answered</span></div>
<div class="legend-item"><div class="legend-box marked"></div><span>Marked</span></div>
<div class="legend-item"><div class="legend-box unanswered"></div><span>Not Answered</span></div>
</div>
<div class="question-grid" id="qg"></div>
<button class="nav-submit-btn" id="nsm"><i class="fas fa-bullseye"></i> SUBMIT TEST</button>
</div>
</div>
<div id="resultsContainer">
<div class="results-header">
<div class="results-icon" id="ri"></div>
<h2 class="results-main-title">🎯 Exam Result Summary</h2>
<div class="results-subtitle">Exam completed · Negative Marking: {nm:g} per wrong answer</div>
<div class="results-score"><span class="results-score-label">Final Score: <span id="rs">0 / {mm}</span></span></div>
<div class="results-percentage" id="rp"></div>
</div>
<div class="stats-grid">
<div class="stat-card total"><div class="stat-value">{mm}</div><div class="stat-label">Total</div></div>
<div class="stat-card correct-card"><div class="stat-value" id="cc">0</div><div class="stat-label">Correct</div></div>
<div class="stat-card incorrect-card"><div class="stat-value" id="ic">0</div><div class="stat-label">Incorrect</div></div>
<div class="stat-card unanswered-card"><div class="stat-value" id="uc">0</div><div class="stat-label">Not Answered</div></div>
</div>
<div class="results-filters" id="resultFilters">
<button class="result-filter active" data-filter="all">📋 All Questions</button>
<button class="result-filter" data-filter="correct">✅ Correct</button>
<button class="result-filter" data-filter="incorrect">❌ Incorrect</button>
<button class="result-filter" data-filter="unanswered">⚪ Not Answered</button>
</div>
<div class="review-list" id="reviewList"></div>
<div class="action-buttons">
<button class="action-btn primary" id="rb"><i class="fas fa-search"></i>Review Answers</button>
<button class="action-btn secondary" id="rsb"><i class="fas fa-redo"></i>Restart Quiz</button>
</div>
</div>
<script>
const qd={{q:[{",".join(qjs)}],m:null,tt:{dt},nm:{nm},sections:{sec_js}}},
st={{cq:0,a:Array(qd.q.length).fill(null),mk:Array(qd.q.length).fill(false),tr:qd.tt,csi:0,sti:null,ti:null,sb:false,rv:false,th:'light'}};

// ── Section helpers ─────────────────────────────────────────────
function getSectionForQ(qi){{
  if(!qd.sections.length) return null;
  for(let i=0;i<qd.sections.length;i++){{
    const s=qd.sections[i];
    if(qi>=s.start&&qi<=s.end) return {{idx:i,sec:s}};
  }}
  return null;
}}
function initSectionTimer(){{
  if(!qd.sections.length) return;
  // Reset each section timer on quiz start
  qd.sections.forEach(s=>{{s.tr=s.timer;}});
  st.csi=0;
  st.tr=qd.sections[0].tr;
}}
function getCurrentSection(){{
  if(!qd.sections.length) return null;
  return qd.sections[st.csi]||null;
}}
function advanceSectionIfNeeded(){{
  if(!qd.sections.length) return;
  const sec=qd.sections[st.csi];
  if(!sec) return;
  // Save remaining time back
  sec.tr=st.tr;
  // Check if user moved beyond this section's last question
  if(st.cq>sec.end&&st.csi<qd.sections.length-1){{
    st.csi++;
    st.tr=qd.sections[st.csi].tr;
    utd();
  }} else if(st.cq<sec.start&&st.csi>0){{
    st.csi--;
    st.tr=qd.sections[st.csi].tr;
    utd();
  }}
}}
// ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded',()=>{{sms();pcc();lt()}});
function lt(){{const t=localStorage.getItem('qt')||'light';st.th=t;document.documentElement.setAttribute('data-theme',t);uti()}}
function tgt(){{st.th=st.th==='light'?'dark':'light';document.documentElement.setAttribute('data-theme',st.th);localStorage.setItem('qt',st.th);uti()}}
function uti(){{const i=document.querySelector('#tt i');if(i)i.className=st.th==='light'?'fas fa-moon':'fas fa-sun'}}
function pcc(){{document.addEventListener('contextmenu',e=>e.preventDefault());document.addEventListener('copy',e=>e.preventDefault());document.addEventListener('cut',e=>e.preventDefault());document.addEventListener('selectstart',e=>{{if(!e.target.tagName.match(/INPUT|TEXTAREA/i))e.preventDefault()}})}}
function sms(){{const mc=document.querySelectorAll('.mode-card'),sb=document.getElementById('sb');mc.forEach(c=>{{c.addEventListener('click',()=>{{mc.forEach(x=>x.classList.remove('selected'));c.classList.add('selected');qd.m=c.dataset.mode;sb.disabled=false}})}}); sb.addEventListener('click',sq)}}
function sq(){{
  const ct=document.getElementById('ct'),ctv=parseInt(ct.value);
  if(!qd.sections.length&&ctv&&ctv>0){{st.tr=ctv*60;qd.tt=ctv*60}}
  document.body.style.overflow='hidden';
  document.getElementById('modeSelection').style.display='none';
  document.getElementById('quizContainer').style.display='block';
  document.getElementById('mb').textContent=qd.m;
  document.getElementById('mb').className='mode-badge '+qd.m;
  iq();
}}
function iq(){{initSectionTimer();rq(0);rqg();stt();sn()}}
function stt(){{
  utd();
  st.ti=setInterval(()=>{{
    st.tr--;
    if(qd.sections.length){{
      const sec=getCurrentSection();
      if(sec) sec.tr=st.tr;
    }}
    utd();
    if(st.tr<=0){{
      if(qd.sections.length&&st.csi<qd.sections.length-1){{
        // Section time up — lock section questions and move to next section
        const sec=qd.sections[st.csi];
        // Force-lock all unanswered in this section (keep nulls, just advance)
        st.csi++;
        st.tr=qd.sections[st.csi].timer;
        qd.sections[st.csi].tr=st.tr;
        rq(qd.sections[st.csi].start);
        utd();
      }} else {{
        clearInterval(st.ti);sbq();
      }}
    }}
    if(st.tr<=60) document.getElementById('td').classList.add('warning');
    else document.getElementById('td').classList.remove('warning');
  }},1000);
}}
function utd(){{
  const m=Math.floor(st.tr/60),s=st.tr%60;
  document.getElementById('tt2').textContent=`${{String(m).padStart(2,'0')}}:${{String(s).padStart(2,'0')}}`;
}}
function rq(i){{
  st.cq=i;
  advanceSectionIfNeeded();
  const q=qd.q[i],qs=document.getElementById('qs');
  let h=`<div class="question-card">`;
  // Section badge
  const si=getSectionForQ(i);
  if(si)h+=`<div class="section-badge"><i class="fas fa-layer-group"></i>${{si.sec.name}}</div>`;
  h+=`<div class="question-number"><i class="fas fa-question-circle"></i>Question ${{i+1}} of ${{qd.q.length}}</div>`;
  if(q.ref)h+=`<div class="question-reference protected-content"><i class="fas fa-info-circle"></i> ${{q.ref}}</div>`;
  h+=`<div class="question-text protected-content">${{q.txt}}</div><div class="options-container">`;
  q.opts.forEach((o,x)=>{{
    let bc='option-btn',ic=String.fromCharCode(65+x);
    const isSel=st.a[i]===x,isCor=x===q.ci,shAns=(qd.m==='practice'&&st.a[i]!==null)||st.sb;
    // Lock options for completed sections in exam mode
    const sectionDone=si&&st.csi>si.idx&&!st.rv;
    if(isSel)bc+=' selected';
    if(shAns||sectionDone){{
      bc+=' disabled';
      if(isCor){{bc+=' correct';ic='<i class="fas fa-check"></i>'}}
      else if(isSel&&!isCor){{bc+=' incorrect';ic='<i class="fas fa-times"></i>'}}
    }}
    h+=`<button class="${{bc}}" data-index="${{x}}" onclick="so(${{x}})"><div class="option-indicator">${{ic}}</div><div class="option-text protected-content">${{o}}</div></button>`;
  }});
  h+=`</div>`;
  const shExp=(qd.m==='practice'&&st.a[i]!==null)||st.sb;
  if(shExp)h+=`<div class="explanation-box" style="display:block"><div class="explanation-header"><i class="fas fa-lightbulb"></i>Explanation</div><div class="explanation-text protected-content">${{q.exp}}</div></div>`;
  h+=`</div>`;
  qs.innerHTML=h;qs.scrollTop=0;up();unb();uqg();
}}
function so(oi){{
  if(st.sb) return;
  // Block input if this question's section time is up
  const si=getSectionForQ(st.cq);
  if(si&&st.csi>si.idx) return;
  if(st.a[st.cq]===oi){{st.a[st.cq]=null}}else{{st.a[st.cq]=oi}}
  rq(st.cq);
}}
function sn(){{document.getElementById('cr').addEventListener('click',clr);document.getElementById('pv').addEventListener('click',np);document.getElementById('nx').addEventListener('click',nn);document.getElementById('mk').addEventListener('click',tm);document.getElementById('sm').addEventListener('click',cs);document.getElementById('nt').addEventListener('click',tnp);document.getElementById('nc').addEventListener('click',tnp);document.getElementById('nsm').addEventListener('click',()=>{{tnp();cs()}});document.getElementById('rb').addEventListener('click',ra);document.getElementById('rsb').addEventListener('click',rs);document.getElementById('tt').addEventListener('click',tgt);document.addEventListener('keydown',e=>{{if(st.sb)return;if(e.key==='ArrowLeft')np();if(e.key==='ArrowRight')nn()}})}}
function np(){{if(st.cq>0)rq(st.cq-1)}}
function nn(){{if(st.cq<qd.q.length-1)rq(st.cq+1)}}
function clr(){{if(st.sb)return;st.a[st.cq]=null;rq(st.cq);uqg();}}
function tm(){{st.mk[st.cq]=!st.mk[st.cq];uqg();const mb=document.getElementById('mk');mb.innerHTML=st.mk[st.cq]?'<i class="fas fa-bookmark"></i> Unmark':'<i class="fas fa-bookmark"></i> Mark'}}
function unb(){{document.getElementById('pv').disabled=st.cq===0;if(st.cq===qd.q.length-1){{document.getElementById('nx').style.display='none';document.getElementById('sm').style.display='flex'}}else{{document.getElementById('nx').style.display='flex';document.getElementById('sm').style.display='none'}}const mb=document.getElementById('mk');mb.innerHTML=st.mk[st.cq]?'<i class="fas fa-bookmark"></i> Unmark':'<i class="fas fa-bookmark"></i> Mark'}}
function up(){{const at=st.a.filter(a=>a!==null).length,pr=((st.cq+1)/qd.q.length)*100;document.getElementById('pt').textContent=`Question ${{st.cq+1}} of ${{qd.q.length}}`;document.getElementById('at').textContent=`Attempted: ${{at}}/${{qd.q.length}}`;document.getElementById('pb').style.width=pr+'%'}}
function rqg(){{
  const g=document.getElementById('qg');
  g.innerHTML='';
  if(qd.sections.length){{
    qd.sections.forEach((sec,si)=>{{
      const lbl=document.createElement('div');
      lbl.className='nav-section-label';
      lbl.textContent=sec.name;
      g.appendChild(lbl);
      for(let i=sec.start;i<=sec.end;i++){{
        const it=document.createElement('div');
        it.className='question-nav-item';
        it.textContent=i+1;
        it.onclick=(()=>{{const idx=i;return()=>{{rq(idx);if(window.innerWidth<768)tnp()}}}})();
        g.appendChild(it);
      }}
    }});
  }} else {{
    qd.q.forEach((_,i)=>{{
      const it=document.createElement('div');
      it.className='question-nav-item';
      it.textContent=i+1;
      it.onclick=()=>{{rq(i);if(window.innerWidth<768)tnp()}};
      g.appendChild(it);
    }});
  }}
}}
function uqg(){{
  const its=document.querySelectorAll('.question-nav-item');
  let qi=0;
  its.forEach(it=>{{
    if(it.classList.contains('nav-section-label')) return;
    const i=parseInt(it.textContent)-1;
    it.className='question-nav-item';
    if(i===st.cq) it.classList.add('current');
    if(st.sb){{
      if(st.a[i]===qd.q[i].ci) it.classList.add('correct');
      else if(st.a[i]!==null) it.classList.add('incorrect');
    }} else {{
      if(st.a[i]!==null) it.classList.add('answered');
      if(st.mk[i]) it.classList.add('marked');
    }}
  }});
}}
function tnp(){{document.getElementById('np').classList.toggle('open')}}
function cs(){{const u=st.a.filter(a=>a===null).length;if(u>0){{const c=window.confirm(`You have ${{u}} unattempted question(s). Do you want to submit?`);if(!c)return}}sbq()}}
function sbq(){{
  clearInterval(st.ti);st.sb=true;
  let c=0,ic=0,u=0,nm=0;
  st.a.forEach((a,i)=>{{if(a===null)u++;else if(a===qd.q[i].ci)c++;else{{ic++;nm+=qd.nm}}}});
  const ts=c-nm,pc=(ts/qd.q.length)*100;
  document.body.style.overflow='auto';
  document.getElementById('quizContainer').style.display='none';
  document.getElementById('resultsContainer').style.display='block';
  document.getElementById('resultsContainer').classList.add('scrollable');
  if(pc>=70){{document.getElementById('ri').innerHTML='<i class="fas fa-trophy" style="color:#fbbf24"></i>';document.getElementById('rt').textContent='Excellent Performance!'}}
  else if(pc>=50){{document.getElementById('ri').innerHTML='<i class="far fa-smile" style="color:#48bb78"></i>';document.getElementById('rt').textContent='Good Job!'}}
  else{{document.getElementById('ri').innerHTML='<i class="far fa-meh" style="color:#f5576c"></i>';document.getElementById('rt').textContent='Keep Practicing!'}}
  document.getElementById('rs').textContent=ts.toFixed(2)+' / '+qd.q.length;
  document.getElementById('rp').textContent=pc.toFixed(1)+'%';
  document.getElementById('cc').textContent=c;
  document.getElementById('ic').textContent=ic;
  document.getElementById('uc').textContent=u;
  document.getElementById('nm').textContent='-'+nm.toFixed(2);
}}
function ra(){{st.rv=true;document.body.style.overflow='hidden';document.getElementById('resultsContainer').style.display='none';document.getElementById('quizContainer').style.display='block';rq(0);uqg()}}
function rs(){{document.body.style.overflow='hidden';location.reload()}}

// Result review UI — added independently; existing quiz functions above remain unchanged.
function renderResultReview(){{
  const list=document.getElementById('reviewList');
  if(!list) return;
  const esc=(v)=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  const ansText=(q,a)=>a===null?'Not Answered':(q.opts[a]??'Not Answered');
  list.innerHTML=qd.q.map((q,i)=>{{
    const a=st.a[i];
    const status=a===null?'unanswered':(a===q.ci?'correct':'incorrect');
    const your=ansText(q,a), cor=ansText(q,q.ci);
    const wrong=status==='incorrect';
    return `<article class="review-card" data-status="${{status}}">
      <div class="review-question-number">Question ${{i+1}}</div>
      <div class="review-question-text">${{esc(q.txt)}}</div>
      <div class="review-answer-box review-your-answer ${{wrong?'wrong':''}}">📝 <strong>Your Answer:</strong> ${{esc(your)}}</div>
      <div class="review-answer-box review-correct-answer">✅ <strong>Correct Answer:</strong> ${{esc(cor)}}</div>
      <div class="review-explanation">💡 <strong>Explanation:</strong> ${{esc(q.exp||'No explanation')}}</div>
    </article>`;
  }}).join('');
  document.querySelectorAll('.result-filter').forEach(btn=>{{
    btn.onclick=()=>{{
      document.querySelectorAll('.result-filter').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const filter=btn.dataset.filter;
      document.querySelectorAll('.review-card').forEach(card=>{{
        card.classList.toggle('review-hidden',filter!=='all'&&card.dataset.status!==filter);
      }});
    }};
  }});
}}

(function installResultReviewObserver(){{
  const target=document.getElementById('resultsContainer');
  if(!target) return;
  const render=()=>{{if(target.style.display==='block') renderResultReview()}};
  new MutationObserver(render).observe(target,{{attributes:true,attributeFilter:['style','class']}});
}})();
</script>
</body>
</html>"""

    # Save and send
    fn = f"{uuid.uuid4().hex}.html"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(html)
    with open(fn, "rb") as f:
        await context.bot.send_document(chat_id=chat_id, document=f, caption=f"{quiz['quiz_name']}\n\nPremium Quiz Bot", protect_content=type)
    import os
    os.remove(fn)
