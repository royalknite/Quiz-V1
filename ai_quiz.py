"""
╔══════════════════════════════════════════════════════════════╗
║   QUIZBOT — AI question generation                           ║
║                                                              ║
║   Reads a PDF / TXT / Image and asks an LLM to produce MCQs ║
║   in the exact .txt format the bot already understands.      ║
║                                                              ║
║   Supported question types:                                  ║
║     - Direct (standard MCQ)                                  ║
║     - Statement (I./II./III. + 👇 separator)                 ║
║     - Assertion-Reason (A: ... R: ...)                       ║
║     - Match the Following ([ Poll : [N/T] ] marker)          ║
║     - Mixed (auto-mix of all types)                          ║
║                                                              ║
║   Provider order:                                            ║
║     1. The user's own Gemini API key (set via /gemini ...)   ║
║     2. Pollinations free OpenAI-compatible API               ║
║     3. Sandeep's free public copilot API                     ║
║                                                              ║
║   No bot-side API key is required for the default path.      ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import aiohttp

CHECK = "\u2705"

SANDEEP_URL = "https://copilotbysandeep.replit.app/chat"
SANDEEP_MAX_CHARS = int(os.getenv("AI_QUIZ_SANDEEP_MAX_CHARS", "6000"))
USER_GEMINI_MAX_CHARS = int(os.getenv("AI_QUIZ_GEMINI_MAX_CHARS", "120000"))
USER_GEMINI_MODEL = os.getenv("AI_QUIZ_USER_GEMINI_MODEL", "gemini-2.5-flash")
MAX_QUESTIONS = int(os.getenv("AI_QUIZ_MAX_QUESTIONS", "100"))
MIN_QUESTIONS = int(os.getenv("AI_QUIZ_MIN_QUESTIONS", "10"))

GEMINI_BATCH_SIZE = int(os.getenv("AI_QUIZ_GEMINI_BATCH", "25"))
GEMINI_RETRIES = int(os.getenv("AI_QUIZ_GEMINI_RETRIES", "3"))

GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv(
        "AI_QUIZ_GEMINI_FALLBACK_MODELS",
        "gemini-2.0-flash,gemini-2.5-flash-lite,gemini-flash-latest",
    ).split(",") if m.strip()
]

SANDEEP_RETRIES = int(os.getenv("AI_QUIZ_SANDEEP_RETRIES", "3"))

POLLINATIONS_URL = "https://text.pollinations.ai/openai"
POLLINATIONS_MODEL = os.getenv("AI_QUIZ_POLLINATIONS_MODEL", "openai")
POLLINATIONS_MAX_CHARS = int(os.getenv("AI_QUIZ_POLLINATIONS_MAX_CHARS", "20000"))
POLLINATIONS_RETRIES = int(os.getenv("AI_QUIZ_POLLINATIONS_RETRIES", "3"))

POLLINATIONS_FALLBACK_MODELS = [
    m.strip() for m in os.getenv(
        "AI_QUIZ_POLLINATIONS_FALLBACK_MODELS",
        "openai-large,openai-fast,mistral",
    ).split(",") if m.strip()
]

# Supported question type identifiers
QTYPE_DIRECT = "direct"
QTYPE_STATEMENT = "statement"
QTYPE_ASSERTION = "assertion"
QTYPE_MATCH = "match"
QTYPE_MIXED = "mixed"

VALID_QTYPES = {QTYPE_DIRECT, QTYPE_STATEMENT, QTYPE_ASSERTION, QTYPE_MATCH, QTYPE_MIXED}


@dataclass
class QuizConfig:
    """Configuration for AI quiz generation."""
    num_questions: int = 25
    difficulty: str = "medium"
    language: str = "English"
    bilingual: bool = False
    question_type: str = QTYPE_MIXED
    page_range: Optional[str] = None  # e.g. "1-5", "3", "all"

    def effective_min(self) -> int:
        return max(MIN_QUESTIONS, self.num_questions)


# ── Source text loaders ────────────────────────────────────────
def extract_text_from_pdf(
    file_path: str,
    max_chars: int,
    page_range: Optional[str] = None,
) -> str:
    """Extract text from PDF, optionally limiting to a page range.

    page_range examples: "1-5", "3", "all", None (= all pages).
    Page numbers are 1-based.
    """
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(f"pypdf not installed: {e}")

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)

    # Determine which pages to extract
    pages_to_use: List[int] = list(range(total_pages))  # 0-based indices
    if page_range and page_range.lower() not in ("all", ""):
        pages_to_use = _parse_page_range(page_range, total_pages)

    chunks: List[str] = []
    for idx in pages_to_use:
        if idx < 0 or idx >= total_pages:
            continue
        try:
            t = reader.pages[idx].extract_text() or ""
        except Exception:
            t = ""
        if t.strip():
            chunks.append(t)

    text = "\n".join(chunks)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


def _parse_page_range(spec: str, total_pages: int) -> List[int]:
    """Parse a page range string like '1-5', '3', '1,3,5-7' → list of 0-based indices."""
    indices: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start = int(bounds[0].strip()) - 1  # convert to 0-based
                end = int(bounds[1].strip()) - 1
                indices.extend(range(max(0, start), min(total_pages - 1, end) + 1))
            except ValueError:
                pass
        else:
            try:
                indices.append(int(part) - 1)
            except ValueError:
                pass
    return sorted(set(indices))


def read_text_file(file_path: str, max_chars: int) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

PDF_OCR_MAX_PAGES = int(os.getenv("AI_QUIZ_PDF_OCR_MAX_PAGES", "10"))
PDF_OCR_DPI = int(os.getenv("AI_QUIZ_PDF_OCR_DPI", "180"))


def is_image_file(file_path: str) -> bool:
    return file_path.lower().endswith(IMAGE_EXTS)


def _load_source(file_path: str, max_chars: int, page_range: Optional[str] = None) -> str:
    if file_path.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_path, max_chars, page_range=page_range)
    return read_text_file(file_path, max_chars)


def _rasterize_pdf_pages(file_path: str, max_pages: int, dpi: int) -> List[str]:
    """Render the first `max_pages` pages of a PDF to PNG files on disk."""
    import fitz  # PyMuPDF

    out_paths: List[str] = []
    doc = fitz.open(file_path)
    try:
        n = min(len(doc), max_pages)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        base = os.path.splitext(file_path)[0]
        for i in range(n):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out = f"{base}.page{i + 1}.png"
            pix.save(out)
            out_paths.append(out)
    finally:
        doc.close()
    return out_paths


async def _ocr_pdf_pages_via_vision(
    file_path: str,
    user_gemini_api_key: Optional[str],
    max_pages: int = PDF_OCR_MAX_PAGES,
    dpi: int = PDF_OCR_DPI,
) -> Tuple[str, str]:
    """Rasterize PDF pages and OCR each via the vision provider chain."""
    page_paths = await asyncio.to_thread(
        _rasterize_pdf_pages, file_path, max_pages, dpi
    )
    if not page_paths:
        raise RuntimeError("PDF has no pages to OCR")

    try:
        chunks: List[str] = []
        provider_used: str = ""
        for idx, p in enumerate(page_paths, start=1):
            print(f"[ai_quiz] OCR PDF page {idx}/{len(page_paths)}")
            text, provider = await extract_text_from_image(
                p, user_gemini_api_key=user_gemini_api_key
            )
            if text.strip():
                chunks.append(text.strip())
            provider_used = provider
        joined = "\n\n".join(chunks).strip()
        if not joined:
            raise RuntimeError("Vision OCR returned no text from any PDF page")
        label = f"{provider_used} (PDF OCR, {len(page_paths)} pages)"
        return joined, label
    finally:
        for p in page_paths:
            try:
                os.remove(p)
            except Exception:
                pass


# ── Vision OCR — extract text from an image via AI ─────────────
_OCR_PROMPT = (
    "You are an OCR + transcription engine. Extract ALL readable text from this "
    "image — questions, paragraphs, notes, equations, lists, captions, etc. "
    "Preserve the original language (Hindi/English/etc). Return ONLY the raw "
    "extracted text, no commentary, no markdown, no headings."
)


def _read_image_b64(file_path: str) -> Tuple[str, str]:
    mime, _ = mimetypes.guess_type(file_path)
    if not mime or not mime.startswith("image/"):
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
        mime = f"image/{ext or 'jpeg'}"
    with open(file_path, "rb") as f:
        data = f.read()
    return mime, base64.b64encode(data).decode("ascii")


def _gemini_ocr_once(file_path: str, api_key: str, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    mime, _b64 = _read_image_b64(file_path)
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    response = client.models.generate_content(
        model=model,
        contents=[
            _OCR_PROMPT,
            types.Part.from_bytes(data=img_bytes, mime_type=mime),
        ],
        config=types.GenerateContentConfig(
            max_output_tokens=8192,
            temperature=0.1,
        ),
    )
    return (response.text or "").strip()


async def _ocr_via_user_gemini(file_path: str, api_key: str) -> str:
    last_err: Optional[BaseException] = None
    for model in [USER_GEMINI_MODEL] + [
        m for m in GEMINI_FALLBACK_MODELS if m != USER_GEMINI_MODEL
    ]:
        for attempt in range(1, GEMINI_RETRIES + 1):
            try:
                text = await asyncio.to_thread(
                    _gemini_ocr_once, file_path, api_key, model
                )
                if text.strip():
                    return text
                raise RuntimeError("Gemini vision returned empty text")
            except Exception as e:
                last_err = e
                if not _is_transient_gemini_error(e):
                    raise
                if attempt < GEMINI_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                else:
                    break
    assert last_err is not None
    raise last_err


async def _ocr_via_pollinations(file_path: str) -> str:
    """Free vision OCR via Pollinations (OpenAI-compatible vision)."""
    mime, b64 = _read_image_b64(file_path)
    body = {
        "model": POLLINATIONS_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
    }
    timeout = aiohttp.ClientTimeout(total=180)
    last_err: Optional[BaseException] = None
    for attempt in range(1, POLLINATIONS_RETRIES + 1):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(POLLINATIONS_URL, json=body) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"Pollinations vision HTTP {resp.status}")
                    data = await resp.json(content_type=None)
            content = data["choices"][0]["message"]["content"]
            if not (content or "").strip():
                raise RuntimeError("Pollinations vision returned empty text")
            return content.strip()
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError, IndexError, TypeError) as e:
            last_err = e
            if attempt >= POLLINATIONS_RETRIES:
                raise
            await asyncio.sleep(2 ** attempt)
    assert last_err is not None
    raise last_err


async def extract_text_from_image(
    file_path: str,
    user_gemini_api_key: Optional[str] = None,
) -> Tuple[str, str]:
    """OCR an image into raw text. Returns (text, provider_used)."""
    failures: List[str] = []
    last_err: Optional[BaseException] = None

    if user_gemini_api_key:
        try:
            print("[ai_quiz] OCR via user's Gemini key")
            text = await _ocr_via_user_gemini(file_path, user_gemini_api_key)
            if text.strip():
                return text, "your Gemini key (vision)"
        except Exception as e:
            last_err = e
            failures.append("your Gemini key")
            print(f"[ai_quiz] Gemini OCR failed: {str(e)[:160]}")

    try:
        print("[ai_quiz] OCR via Pollinations vision (free)")
        text = await _ocr_via_pollinations(file_path)
        if text.strip():
            label = "Pollinations vision (free)"
            if failures:
                label += f" (after {', '.join(failures)} failed)"
            return text, label
    except Exception as e:
        last_err = e
        print(f"[ai_quiz] Pollinations OCR failed: {str(e)[:160]}")

    msg = "Couldn't read text from this image."
    if last_err:
        msg += f" Last error: {str(last_err)[:160]}"
    raise RuntimeError(msg)


# ── Comprehensive system prompt ────────────────────────────────
_SYSTEM_PROMPT = """Act as an expert educational content extractor and quiz generator.
Based strictly on the USER CONFIGURATION below, process the input.

1. Intelligent Extraction vs. Generation:
   - If the document already contains MCQs, extract and properly reformat them into the required template.
   - If the document contains theory, notes, or explanations, generate high-quality MCQs based on the concepts and competitive exam PYQ patterns.
   - If only a topic is provided, generate questions using internal knowledge while maintaining realistic exam-style difficulty and structure.

2. Source Material & Page Scope:
   - If Page Number(s) / Range is specified and not set to All, strictly use only those pages.
   - Ignore all content outside the requested page range.

3. Language Rules:
   - If a single language is requested, output entirely in that language.
   - If bilingual mode is requested, every line must contain both languages separated using / .
   - Maintain natural grammar and exam-style wording in both languages.

4. Question Types:

   A. STATEMENT TYPE:

      Introductory question line

      I. Statement 1
      II. Statement 2
      III. Statement 3 (if applicable)

      Which of the above statements is/are correct?

      👇
      A) option
      B) option
      C) option
      D) option

      Ex: brief explanation

      WRONG (never do this):
        [ Poll : [3/24] Introductory question? ]
        - I. Statement one.
        - II. Statement two.
        - Final question?
        - 👇
        - option A
        - option B
        - option C
        - option D

      RIGHT (always do this):
        Introductory question?

        I. Statement one.
        II. Statement two.

        Which of the above is correct?

        👇
        A) option A
        B) option B ✅
        C) option C
        D) option D

        Ex: explanation

      Rules:
      - NEVER put the question text inside the [ Poll : [...] ] marker.
      - NEVER use dash ( - ) as option prefix; always use A) B) C) D).
      - NEVER list the 👇 separator as a dash bullet item.
      - The [ Poll : [N/T] ] marker is ONLY used for Match-the-Following questions.
      - Every statement (I. II. III.) must appear on its own line as part of the question body.
      - Exactly 4 options labeled A) B) C) D), one marked ✅.

   B. ASSERTION-REASON TYPE:

      Assertion (A): ...

      Reason (R): ...

      A) Both A and R are true, and R is the correct explanation of A
      B) Both A and R are true, but R is NOT the correct explanation of A
      C) A is true, but R is false
      D) A is false, but R is true

      Ex: brief explanation

   C. MATCH THE FOLLOWING TYPE:

      Match the following correctly

      Item 1 → i. Match 1
      Item 2 → ii. Match 2
      Item 3 → iii. Match 3
      Item 4 → iv. Match 4

      Choose the correct code from below.

      [ Poll : [N/T] ]

      A) combination
      B) combination
      C) combination
      D) combination

      Ex: brief explanation

      Rules:
      - Each Item → Match pair MUST appear on its own separate line.
      - NEVER compress all items into a single line.
      - The [ Poll : [N/T] ] marker must appear on its own line, with nothing else on that line.
      - [ Poll : [N/T] ] is ONLY for this question type, never for Statement or Direct types.
      - Options must use A) B) C) D) labels, never dashes.

      WRONG (never do this):
        [ Poll : [3/24] Match the following? ]
        - Item 1 → i. Match 1, Item 2 → ii. Match 2, Item 3 → iii. Match 3, Item 4 → iv. Match 4
        - A) ...  - B) ...  - C) ...  - D) ...

      RIGHT (always do this):
        Match the following correctly

        Item 1 → i. Match 1
        Item 2 → ii. Match 2
        Item 3 → iii. Match 3
        Item 4 → iv. Match 4

        Choose the correct code from below.

        [ Poll : [N/T] ]

        A) 1-i, 2-ii, 3-iii, 4-iv ✅
        B) 1-ii, 2-i, 3-iv, 4-iii
        C) 1-iii, 2-iv, 3-i, 4-ii
        D) 1-iv, 2-iii, 3-ii, 4-i

        Ex: explanation

   D. DIRECT TYPE:

      Question text

      A) option
      B) option
      C) option
      D) option

      Ex: brief explanation

   E. MIXED TYPE:
      Mix different question styles naturally across the quiz.

5. Correct Answer Rules:
   - The correct answer does NOT need to always be option A.
   - Randomize the correct answer position naturally across A, B, C, and D.
   - Ensure exactly ONE option is correct.
   - Mark the correct answer by appending  ✅  at the end of that option line.
   - Wrong options must be realistic and competitive-exam quality.
   - Avoid obvious elimination patterns.

6. Explanation Rules:
   - Keep explanations short, factual, and exam-oriented.
   - Do not make explanations excessively long.
   - Always provide a concise one-line explanation after Ex: .

7. Formatting Rules:
   - Plain text only.
   - No markdown.
   - No code blocks.
   - No decorative symbols or bullets.
   - Do NOT use: | * # or bullet points.
   - Separate each question block with exactly ONE blank line.
   - Do not include introductory text, greetings, summaries, or closing notes.
   - Entire output must be generated in ONE response.
   - Do not split output into multiple messages.
   - Do not number questions with Q1 / 1. / Question 1 etc.

8. Matching-Type Compatibility Rules:
   - For MATCH THE FOLLOWING type, ALWAYS include:
         [ Poll : [N/T] ]
     exactly in this format on its own line before the options.
   - Maintain proper arrow formatting using: →
   - Do not replace arrows with other symbols.

9. Quality Rules:
   - Questions must resemble real competitive exam patterns.
   - Maintain conceptual accuracy.
   - Avoid repeated questions.
   - Ensure difficulty matches the requested level.
   - Avoid vague or ambiguous wording.
   - Use clean and readable formatting.

10. Extraction Priority:
   - If existing questions are present in the source, prioritize extraction over regeneration.
   - Preserve factual correctness from the source material.
   - Reformat messy OCR text into clean structured MCQs.

11. Output Consistency:
   - Every question must contain exactly 4 options labeled A) B) C) D).
   - Every question must contain only one correct answer marked with ✅ at the end.
   - Maintain consistent spacing and formatting throughout the output.

12. PDF/OCR Formatting Recovery:
   - If imported PDF/OCR text has broken or missing option labels, automatically reconstruct them as:
         A) option
         B) option
         C) option
         D) option
   - Detect malformed formats such as A. / A: / (A) / A - / Option A
     and normalize them into: A) text

13. Final Strict Validation:
   - Every question has exactly 4 options.
   - Only one option is correct (marked ✅).
   - Matching questions contain [ Poll : [N/T] ] marker.
   - No markdown symbols present.
   - No broken OCR formatting remains.
   - No duplicate options within the same question.
   - No empty explanations.
   - Output is parser-friendly and Telegram-compatible.

14. Telegram Quiz Bot Feature Awareness:
   The generated quiz content must remain fully compatible with advanced Telegram quiz bot systems.
   - Minimum 10 questions required before quiz completion unless explicitly overridden by user.
   - Quiz structure must remain suitable for public sharing via quiz codes and deep links.
   - Keep questions concise enough for fast timed answering (45s, 60s, 120s modes).
   PDF Import Recovery System:
   - Automatically detect and repair broken OCR/PDF option formatting.
   - If option brackets are missing, reconstruct them automatically.
   - Malformed formats that must be auto-corrected:
         A option / B option / C option / D option
         A. / B. / C. / D.
         (A) / (B) / (C) / (D)
         A: / B: / C: / D:
         Option A / Option B / Option C / Option D
   - Normalize all malformed options into: A) option  B) option  C) option  D) option

15. Quiz Editing and Management Compatibility:
   Generated quizzes must support advanced editing systems including:
   Quiz Settings Editing: Quiz Name, Timer, Free/Paid mode, Negative marking, Promo link.
   Question Management: View, Edit, Add new, Delete single, Delete multiple questions.
   Question Editor Compatibility: Replace question text, Replace options, Add/Edit explanations, Delete individually.
   Advanced Features: Shuffle questions, Shuffle options, Export/import, Permission management, MongoDB storage.

16. Parser Safety Rules:
   Ensure formatting remains stable for automatic parsers.
   - Never merge two questions together.
   - Never skip option labels.
   - Never generate more than four options.
   - Never generate empty options.
   - Maintain predictable spacing.
   - Keep poll markers isolated on their own line.
   - Avoid malformed numbering.
   - Avoid duplicate explanations.
   - Ensure every question block can be independently parsed and edited later.
"""


def _build_user_config_block(cfg: QuizConfig) -> str:
    """Build the USER CONFIGURATION section appended to the system prompt."""
    lang_line = (
        f"Both {cfg.language} and English (bilingual, separate with / )"
        if cfg.bilingual
        else cfg.language
    )
    qtype_label = {
        QTYPE_DIRECT: "D. DIRECT TYPE only",
        QTYPE_STATEMENT: "A. STATEMENT TYPE only",
        QTYPE_ASSERTION: "B. ASSERTION-REASON TYPE only",
        QTYPE_MATCH: "C. MATCH THE FOLLOWING TYPE only",
        QTYPE_MIXED: "E. MIXED TYPE (mix all styles)",
    }.get(cfg.question_type, "E. MIXED TYPE (mix all styles)")

    page_line = (
        f"{cfg.page_range}"
        if cfg.page_range and cfg.page_range.lower() not in ("all", "")
        else "All"
    )

    return (
        f"\nUSER CONFIGURATION:\n"
        f"Number of Questions: {cfg.num_questions}\n"
        f"Difficulty Level: {cfg.difficulty}\n"
        f"Language: {lang_line}\n"
        f"Question Type: {qtype_label}\n"
        f"Page Number(s) / Range: {page_line}\n"
        f"Minimum Questions: Generate at least {max(MIN_QUESTIONS, cfg.num_questions)} questions.\n"
        f"If source material is insufficient, generate additional relevant questions to meet the minimum.\n"
    )


def _build_native_prompt(source_text: str, cfg: QuizConfig) -> str:
    """Build the comprehensive plain-text prompt using the system instruction + user config."""
    user_cfg = _build_user_config_block(cfg)
    return (
        _SYSTEM_PROMPT
        + user_cfg
        + f"\nSOURCE MATERIAL:\n<SRC>\n{source_text}\n</SRC>\n\n"
        "OUTPUT (quiz questions only, no intro/outro):"
    )


def _build_json_prompt(source_text: str, cfg: QuizConfig) -> str:
    """JSON-format prompt for providers that reliably emit JSON (Gemini)."""
    user_cfg = _build_user_config_block(cfg)
    return (
        f"You are an expert exam-question writer.\n"
        + user_cfg
        + f"\nRules for JSON output:\n"
        f"- Each question must have EXACTLY 4 options.\n"
        f"- Exactly ONE option is correct; set correct_index to 0=A, 1=B, 2=C, 3=D.\n"
        f"- Randomize the correct answer position across questions.\n"
        f"- For STATEMENT type questions, embed the full statement block in the question field.\n"
        f"- For MATCH THE FOLLOWING, embed all matching items and [ Poll : [N/T] ] in the question field.\n"
        f"- For ASSERTION-REASON, embed both Assertion and Reason in the question field.\n"
        f"- No markdown. No letter prefixes (A), 1.) in options — just plain option text.\n"
        f"- question text ≤ 600 chars; each option ≤ 120 chars; explanation ≤ 200 chars.\n"
        f"- Minimum {max(MIN_QUESTIONS, cfg.num_questions)} questions.\n"
        f"- Language: {'bilingual ' + cfg.language + '/English' if cfg.bilingual else cfg.language}.\n"
        f"- Difficulty: {cfg.difficulty}.\n\n"
        f"Return ONLY this JSON (no prose, no code fences):\n"
        f'{{"questions":[{{"question":"...","options":["o1","o2","o3","o4"],'
        f'"correct_index":0,"explanation":"..."}}]}}\n\n'
        f"SOURCE MATERIAL:\n<SRC>\n{source_text}\n</SRC>"
    )


# ── Legacy prompt builders (kept for backward compat) ──────────
def _build_prompt(text: str, num_questions: int, difficulty: str) -> str:
    cfg = QuizConfig(num_questions=num_questions, difficulty=difficulty)
    return _build_json_prompt(text, cfg)


def _build_plain_prompt(text: str, num_questions: int, difficulty: str) -> str:
    cfg = QuizConfig(num_questions=num_questions, difficulty=difficulty)
    return _build_native_prompt(text, cfg)


# ── Output cleanup and normalization ──────────────────────────
_MALFORMED_OPTION_RE = re.compile(
    r"^[\s]*(?:option\s*)?[\(\[]?([A-Da-d])[\)\].\:\-]\s+",
    re.IGNORECASE,
)


def _normalize_option_label(line: str) -> Optional[Tuple[str, str]]:
    """Detect a malformed option line and return (letter, text) or None."""
    m = _MALFORMED_OPTION_RE.match(line)
    if m:
        letter = m.group(1).upper()
        text = line[m.end():].strip()
        return letter, text
    return None


def _clean_native_output(raw: str) -> str:
    """Clean and normalize raw AI output:
    - Normalize malformed option labels to A) / B) / C) / D)
    - Remove markdown artifacts
    - Ensure ✅ marks remain intact
    - Remove leading/trailing blank lines
    """
    lines = raw.splitlines()
    cleaned: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Remove markdown headings / bullets / bold markers
        stripped = re.sub(r"^#+\s*", "", stripped)
        stripped = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", stripped)
        stripped = re.sub(r"^[-•]\s+", "", stripped)

        # Normalize malformed option labels
        parsed = _normalize_option_label(stripped)
        if parsed:
            letter, text = parsed
            # Check if the text contains ✅
            correct_marker = ""
            if "✅" in text or "✔" in text or "✓" in text:
                text = re.sub(r"[✅✔✓]", "", text).strip()
                correct_marker = " ✅"
            stripped = f"{letter}) {text}{correct_marker}"

        cleaned.append(stripped)

    # Re-join and normalise consecutive blank lines to exactly one
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ── JSON parsing helpers ───────────────────────────────────────
def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _try_parse_json(s: str):
    """Try several strategies to extract a parseable JSON value from `s`."""
    s = s.strip()
    if not s:
        return None

    try:
        return json.loads(s)
    except Exception:
        pass

    for opener, closer in (("{", "}"), ("[", "]")):
        start = s.find(opener)
        if start < 0:
            continue
        end = s.rfind(closer)
        while end > start:
            candidate = s[start:end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                end = s.rfind(closer, start, end)

    for opener, closer in (("{", "}"), ("[", "]")):
        depth = 0
        start = -1
        for i, ch in enumerate(s):
            if ch == opener:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == closer and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = s[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except Exception:
                        pass
                    start = -1
    return None


_CORRECT_FIELD_NAMES = (
    "correct_index", "correctIndex", "answer_index", "answerIndex",
    "correct", "answer", "correct_answer", "correctAnswer",
)


def _coerce_correct_index(q: dict, opts: List[str]) -> Optional[int]:
    """Normalize various correct-answer representations to int 0..3."""
    for key in _CORRECT_FIELD_NAMES:
        if key not in q:
            continue
        v = q[key]
        if isinstance(v, bool):
            continue
        if isinstance(v, int) and 0 <= v < 4:
            return v
        if isinstance(v, int) and 1 <= v <= 4:
            return v - 1
        if isinstance(v, str):
            vs = v.strip()
            if vs.isdigit():
                n = int(vs)
                if 0 <= n < 4:
                    return n
                if 1 <= n <= 4:
                    return n - 1
            letter = vs[0].upper() if vs else ""
            if letter in "ABCD":
                return ord(letter) - ord("A")
            for idx, o in enumerate(opts):
                if o.strip().lower() == vs.lower():
                    return idx
    return None


def _parse_questions_json(raw: str) -> List[dict]:
    cleaned = _strip_code_fence(raw)
    data = _try_parse_json(cleaned)
    if data is None:
        raise ValueError("AI response was not valid JSON")

    if isinstance(data, dict):
        questions = data.get("questions") or data.get("mcqs") or data.get("data")
        if not isinstance(questions, list):
            questions = [data]
    elif isinstance(data, list):
        questions = data
    else:
        raise ValueError("AI response missing 'questions' list")

    cleaned_qs: List[dict] = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        text = (q.get("question") or q.get("q") or q.get("text") or "").strip()
        opts = q.get("options") or q.get("choices") or q.get("opts") or []
        expl = (q.get("explanation") or q.get("explain") or q.get("ex") or "").strip()

        if not text or not isinstance(opts, list) or len(opts) != 4:
            continue
        opts = [str(o).strip() for o in opts]
        opts = [re.sub(r"^\s*[\(\[]?[A-Da-d1-4][\)\].\:\-]\s*", "", o).strip() for o in opts]
        if not all(opts):
            continue

        ci = _coerce_correct_index(q, opts)
        if ci is None:
            continue

        cleaned_qs.append(
            {
                "question": text,
                "options": opts,
                "correct_index": ci,
                "explanation": expl,
            }
        )
    return cleaned_qs


# ── Native plain-text MCQ parser ───────────────────────────────
def _parse_plain_text_mcqs(raw: str) -> List[dict]:
    """Parse the bot's native plain-text MCQ block format.

    Handles:
      - Standard format: question + 4 option lines + optional Ex:
      - Statement type: question with I./II./III. lines + 👇 separator + options
      - Assertion-Reason type: Assertion/Reason block + options
      - Match the Following type: items with → arrows + [ Poll : [N/T] ] marker + options
    """
    blocks = re.split(r"\n\s*\n+", raw.strip())
    out: List[dict] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 5:
            continue

        # Find all option lines (A) / B) / C) / D) pattern)
        opt_indices = [
            i for i, ln in enumerate(lines)
            if re.match(r"^[A-Da-d]\)", ln)
        ]

        if len(opt_indices) < 4:
            continue

        # The question block is everything before the first option
        first_opt = opt_indices[0]
        question_lines = lines[:first_opt]

        # Remove 👇 separator lines from the question block
        question_lines = [
            ln for ln in question_lines
            if not re.match(r"^👇", ln)
        ]
        # Remove [ Poll : [N/T] ] marker from question lines (it appears before options)
        question_lines = [
            ln for ln in question_lines
            if not re.match(r"^\[\s*Poll\s*:", ln, re.IGNORECASE)
        ]

        question = "\n".join(question_lines).strip()

        # Strip Q1. / 1) / Q. prefix from first line only
        question = re.sub(r"^(Q\s*\d*[\.\:\)]?|\d+[\.\:\)])\s*", "", question).strip()

        # Extract the 4 option lines
        option_lines = [lines[i] for i in opt_indices[:4]]

        # Collect explanation from lines after options
        explanation = ""
        extra_start = opt_indices[3] + 1
        for ln in lines[extra_start:]:
            if re.match(r"^(ex|explanation|expl)[\s\:\-]+", ln, re.IGNORECASE):
                explanation = re.sub(
                    r"^(ex|explanation|expl)[\s\:\-]+", "", ln, flags=re.IGNORECASE
                ).strip()
                break

        opts: List[str] = []
        correct_idx: Optional[int] = None
        for idx, ln in enumerate(option_lines):
            is_correct = bool(re.search(r"(✅|✔|✓|\*|\[correct\]|\(correct\))", ln, re.IGNORECASE))
            cleaned = re.sub(r"(✅|✔|✓|\*|\[correct\]|\(correct\))", "", ln, flags=re.IGNORECASE)
            cleaned = re.sub(r"^\s*[\(\[]?[A-Da-d1-4][\)\].\:\-]\s*", "", cleaned).strip()
            if not cleaned:
                continue
            opts.append(cleaned)
            if is_correct and correct_idx is None:
                correct_idx = idx

        if len(opts) != 4 or correct_idx is None:
            continue

        out.append({
            "question": question,
            "options": opts,
            "correct_index": correct_idx,
            "explanation": explanation,
        })
    return out


def _count_questions_in_native(text: str) -> int:
    """Count how many question blocks appear in native format text."""
    blocks = re.split(r"\n\s*\n+", text.strip())
    count = 0
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        opt_count = sum(1 for ln in lines if re.match(r"^[A-Da-d]\)", ln))
        if opt_count >= 4:
            count += 1
    return count


# ── Public API ─────────────────────────────────────────────────
def format_questions_as_txt(questions: List[dict]) -> str:
    """Render parsed questions in the bot's native .txt block format."""
    blocks: List[str] = []
    for q in questions:
        lines: List[str] = [q["question"]]
        for idx, opt in enumerate(q["options"]):
            label = chr(ord("A") + idx) + ")"
            if idx == q["correct_index"]:
                lines.append(f"{label} {opt} {CHECK}")
            else:
                lines.append(f"{label} {opt}")
        if q.get("explanation"):
            lines.append(f"Ex: {q['explanation']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# ── Provider implementations ───────────────────────────────────

# Provider: Sandeep
async def _sandeep_call_once_with_prompt(prompt: str) -> str:
    """Single Sandeep request → returns the raw inner text string."""
    params = urllib.parse.urlencode({"text": prompt})
    url = f"{SANDEEP_URL}?{params}"
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Sandeep API HTTP {resp.status}")
            payload = await resp.json(content_type=None)
    if not isinstance(payload, dict) or not payload.get("status"):
        raise RuntimeError("Sandeep API returned status=false")
    inner = payload.get("text") or ""
    if not inner.strip():
        raise RuntimeError("Sandeep API returned empty text")
    return inner


async def _generate_via_sandeep(
    text: str, cfg: QuizConfig
) -> str:
    """Generate questions via Sandeep in native plain-text format.
    Returns the raw cleaned native text."""
    prompt = _build_native_prompt(text[:SANDEEP_MAX_CHARS], cfg)
    last_err: Optional[BaseException] = None

    for attempt in range(1, SANDEEP_RETRIES + 1):
        try:
            inner = await _sandeep_call_once_with_prompt(prompt)
            cleaned = _clean_native_output(inner)
            if _count_questions_in_native(cleaned) > 0:
                return cleaned
            if attempt < SANDEEP_RETRIES:
                await asyncio.sleep(2 ** attempt)
                continue
            break
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
            last_err = e
            transient = (
                isinstance(e, (aiohttp.ClientError, asyncio.TimeoutError))
                or any(tok in str(e) for tok in ("502", "503", "504", "timeout"))
            )
            print(f"[ai_quiz] Sandeep error (attempt {attempt}/{SANDEEP_RETRIES}): {str(e)[:160]}")
            if attempt >= SANDEEP_RETRIES or not transient:
                break
            await asyncio.sleep(2 ** attempt)

    if last_err:
        raise last_err
    raise RuntimeError("Sandeep returned no parseable questions")


# Provider: Pollinations
async def _pollinations_raw_call(prompt: str, model: str) -> str:
    """Single Pollinations request → returns the raw content string."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(POLLINATIONS_URL, json=body) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Pollinations API HTTP {resp.status}")
            data = await resp.json(content_type=None)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Pollinations returned unexpected payload shape")
    if not (content or "").strip():
        raise RuntimeError("Pollinations returned empty content")
    return content


async def _generate_via_pollinations(
    text: str, cfg: QuizConfig
) -> str:
    """Generate questions via Pollinations in native plain-text format."""
    prompt = _build_native_prompt(text[:POLLINATIONS_MAX_CHARS], cfg)
    models_to_try = [POLLINATIONS_MODEL] + [
        m for m in POLLINATIONS_FALLBACK_MODELS if m != POLLINATIONS_MODEL
    ]
    last_err: Optional[BaseException] = None

    for model in models_to_try:
        for attempt in range(1, POLLINATIONS_RETRIES + 1):
            try:
                content = await _pollinations_raw_call(prompt, model)
                cleaned = _clean_native_output(content)
                if _count_questions_in_native(cleaned) > 0:
                    return cleaned
                if attempt < POLLINATIONS_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
                last_err = e
                transient = (
                    isinstance(e, (aiohttp.ClientError, asyncio.TimeoutError))
                    or any(tok in str(e) for tok in ("502", "503", "504", "timeout"))
                )
                print(
                    f"[ai_quiz] Pollinations[{model}] error "
                    f"(attempt {attempt}/{POLLINATIONS_RETRIES}): {str(e)[:160]}"
                )
                if attempt >= POLLINATIONS_RETRIES or not transient:
                    break
                await asyncio.sleep(2 ** attempt)

    if last_err:
        raise last_err
    raise RuntimeError(
        f"Pollinations returned no parseable questions across {len(models_to_try)} models"
    )


# Provider: User Gemini key
_TRANSIENT_TOKENS = (
    "503", "429", "unavailable", "overloaded", "resource_exhausted",
    "rate limit", "deadline", "timeout",
)


def _is_transient_gemini_error(err: BaseException) -> bool:
    s = str(err).lower()
    return any(tok in s for tok in _TRANSIENT_TOKENS)


def _gemini_call_once(
    text: str,
    cfg: QuizConfig,
    api_key: str,
    avoid_questions: Optional[List[str]] = None,
    model: str = USER_GEMINI_MODEL,
    use_json: bool = True,
) -> str:
    """Single Gemini call. Returns native plain-text or JSON string."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    if use_json:
        prompt = _build_json_prompt(text, cfg)
        if avoid_questions:
            sample = "\n".join(f"- {q[:140]}" for q in avoid_questions[:40])
            prompt += (
                "\n\nIMPORTANT: Do NOT repeat or paraphrase any of these "
                f"already-generated questions:\n{sample}"
            )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=32768,
                response_mime_type="application/json",
                temperature=0.6,
            ),
        )
    else:
        prompt = _build_native_prompt(text, cfg)
        if avoid_questions:
            sample = "\n".join(f"- {q[:140]}" for q in avoid_questions[:40])
            prompt += (
                "\n\nDo NOT repeat or paraphrase any of these "
                f"already-generated questions:\n{sample}"
            )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=32768,
                temperature=0.6,
            ),
        )

    raw = response.text or ""
    if not raw.strip():
        raise RuntimeError("Gemini returned an empty response")
    return raw


async def _gemini_call_with_retry(
    text: str,
    cfg: QuizConfig,
    api_key: str,
    avoid_questions: Optional[List[str]] = None,
) -> str:
    """Try Gemini with JSON first, fall back to native plain-text if JSON fails.
    Returns native plain-text output."""
    models_to_try = [USER_GEMINI_MODEL] + [
        m for m in GEMINI_FALLBACK_MODELS if m != USER_GEMINI_MODEL
    ]
    last_err: Optional[BaseException] = None

    # Phase 1: JSON output
    for model in models_to_try:
        for attempt in range(1, GEMINI_RETRIES + 1):
            try:
                raw = await asyncio.to_thread(
                    _gemini_call_once,
                    text, cfg, api_key, avoid_questions, model, True,
                )
                try:
                    questions = _parse_questions_json(raw)
                    if questions:
                        return format_questions_as_txt(questions)
                except ValueError:
                    pass
                # JSON parse failed — try next attempt
                if attempt < GEMINI_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except Exception as e:
                last_err = e
                if not _is_transient_gemini_error(e):
                    raise
                if attempt < GEMINI_RETRIES:
                    backoff = 2 ** attempt
                    print(
                        f"[ai_quiz] Gemini[{model}] JSON transient error "
                        f"(attempt {attempt}/{GEMINI_RETRIES}): {str(e)[:160]} — "
                        f"retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                else:
                    print(f"[ai_quiz] Gemini[{model}] JSON exhausted after {GEMINI_RETRIES} attempts")
                    break

    # Phase 2: Native plain-text output
    print("[ai_quiz] Gemini JSON path failed — trying native plain-text format")
    for model in models_to_try:
        for attempt in range(1, GEMINI_RETRIES + 1):
            try:
                raw = await asyncio.to_thread(
                    _gemini_call_once,
                    text, cfg, api_key, avoid_questions, model, False,
                )
                cleaned = _clean_native_output(raw)
                if _count_questions_in_native(cleaned) > 0:
                    return cleaned
                if attempt < GEMINI_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                break
            except Exception as e:
                last_err = e
                if not _is_transient_gemini_error(e):
                    raise
                if attempt < GEMINI_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                else:
                    break

    if last_err:
        raise last_err
    raise RuntimeError("Gemini returned no parseable questions in JSON or plain-text mode")


async def _generate_via_user_gemini(
    text: str, cfg: QuizConfig, api_key: str
) -> str:
    """Batched generation for large question counts. Returns native plain-text."""
    remaining = cfg.num_questions
    all_blocks: List[str] = []
    seen: set = set()

    def _norm(q: str) -> str:
        return re.sub(r"\s+", " ", q.strip().lower())[:200]

    batch_idx = 0
    while remaining > 0:
        batch_idx += 1
        batch_cfg = QuizConfig(
            num_questions=min(GEMINI_BATCH_SIZE, remaining),
            difficulty=cfg.difficulty,
            language=cfg.language,
            bilingual=cfg.bilingual,
            question_type=cfg.question_type,
            page_range=cfg.page_range,
        )
        avoid = []
        for block in all_blocks:
            first_line = block.strip().splitlines()[0] if block.strip() else ""
            if first_line:
                avoid.append(first_line)

        try:
            batch_txt = await _gemini_call_with_retry(
                text[:USER_GEMINI_MAX_CHARS], batch_cfg, api_key,
                avoid_questions=avoid if avoid else None,
            )
        except Exception as e:
            if all_blocks:
                print(
                    f"[ai_quiz] Gemini batch {batch_idx} failed ({str(e)[:160]}); "
                    f"returning {len(all_blocks)} partial blocks"
                )
                break
            raise

        # Split batch result into individual question blocks
        new_blocks = [
            b.strip() for b in re.split(r"\n\s*\n+", batch_txt.strip())
            if b.strip() and _count_questions_in_native(b) > 0
        ]

        added = 0
        for b in new_blocks:
            key = _norm(b.splitlines()[0] if b.splitlines() else b)
            if key in seen:
                continue
            seen.add(key)
            all_blocks.append(b)
            added += 1

        remaining = cfg.num_questions - len(all_blocks)

        if added == 0:
            print(
                f"[ai_quiz] Gemini batch {batch_idx} produced no new questions; "
                f"stopping at {len(all_blocks)}"
            )
            break

    return "\n\n".join(all_blocks[:cfg.num_questions])


# ── High-level API ─────────────────────────────────────────────
async def generate_questions_txt_from_file(
    file_path: str,
    num_questions: int = 25,
    difficulty: str = "medium",
    user_gemini_api_key: Optional[str] = None,
    language: str = "English",
    bilingual: bool = False,
    question_type: str = QTYPE_MIXED,
    page_range: Optional[str] = None,
) -> Tuple[str, int, str]:
    """High-level helper: file → (native_txt, count, provider_name).

    Accepts .pdf, .txt, and image files (.jpg/.png/.webp/etc).

    New parameters:
        language      — output language (e.g. "Hindi", "English")
        bilingual     — if True, output both language and English
        question_type — one of: "direct", "statement", "assertion", "match", "mixed"
        page_range    — PDF page range e.g. "1-5", "3", "all" or None for all
    """
    # Validate / normalise question type
    if question_type not in VALID_QTYPES:
        question_type = QTYPE_MIXED

    n = max(MIN_QUESTIONS, min(int(num_questions), MAX_QUESTIONS))
    cfg = QuizConfig(
        num_questions=n,
        difficulty=difficulty,
        language=language,
        bilingual=bilingual,
        question_type=question_type,
        page_range=page_range,
    )

    # Image files: OCR first, then generate
    if is_image_file(file_path):
        ocr_text, ocr_provider = await extract_text_from_image(
            file_path, user_gemini_api_key=user_gemini_api_key
        )
        tmp_txt = file_path + ".ocr.txt"
        with open(tmp_txt, "w", encoding="utf-8") as f:
            f.write(ocr_text)
        try:
            txt, count, gen_provider = await generate_questions_txt_from_file(
                tmp_txt,
                num_questions=n,
                difficulty=difficulty,
                user_gemini_api_key=user_gemini_api_key,
                language=language,
                bilingual=bilingual,
                question_type=question_type,
                page_range=page_range,
            )
        finally:
            try:
                os.remove(tmp_txt)
            except Exception:
                pass
        return txt, count, f"{ocr_provider} → {gen_provider}"

    # Load source text
    base_source = _load_source(file_path, USER_GEMINI_MAX_CHARS, page_range=page_range)

    # Scanned PDF fallback: rasterize + OCR
    used_pdf_ocr_provider: Optional[str] = None
    if not base_source.strip() and file_path.lower().endswith(".pdf"):
        print("[ai_quiz] PDF has no extractable text — falling back to OCR")
        try:
            base_source, used_pdf_ocr_provider = await _ocr_pdf_pages_via_vision(
                file_path, user_gemini_api_key=user_gemini_api_key
            )
            if len(base_source) > USER_GEMINI_MAX_CHARS:
                base_source = base_source[:USER_GEMINI_MAX_CHARS]
        except Exception as e:
            raise RuntimeError(
                f"This PDF is scanned/image-based and OCR also failed: {str(e)[:200]}"
            )

    if not base_source.strip():
        raise RuntimeError(
            "Couldn't read any text — is the PDF scanned/image-based?"
        )

    # Build provider chain (priority order)
    chain: List[Tuple[str, object]] = []

    if user_gemini_api_key:
        gem_src = base_source[:USER_GEMINI_MAX_CHARS]
        chain.append((
            "your Gemini key",
            lambda s=gem_src, c=cfg, k=user_gemini_api_key: _generate_via_user_gemini(s, c, k),
        ))

    poll_src = base_source[:POLLINATIONS_MAX_CHARS]
    chain.append((
        "Pollinations AI (free)",
        lambda s=poll_src, c=cfg: _generate_via_pollinations(s, c),
    ))

    sand_src = base_source[:SANDEEP_MAX_CHARS]
    chain.append((
        "Sandeep AI (free)",
        lambda s=sand_src, c=cfg: _generate_via_sandeep(s, c),
    ))

    result_txt: str = ""
    used_provider: str = ""
    last_err: Optional[BaseException] = None
    failures: List[str] = []

    for provider_name, run in chain:
        try:
            print(f"[ai_quiz] Trying provider: {provider_name}")
            raw = await run()
            if raw and _count_questions_in_native(raw) > 0:
                result_txt = raw
                used_provider = provider_name
                if failures:
                    used_provider += f" (after {', '.join(failures)} failed)"
                break
            failures.append(provider_name)
        except Exception as e:
            last_err = e
            print(f"[ai_quiz] Provider {provider_name} failed: {str(e)[:120]}")
            failures.append(provider_name)
            continue

    if not result_txt:
        if last_err:
            raise RuntimeError(
                f"All AI providers are temporarily unavailable. "
                f"Last error: {str(last_err)[:160]}"
            )
        raise RuntimeError("AI did not return any valid questions")

    if used_pdf_ocr_provider:
        used_provider = f"{used_pdf_ocr_provider} → {used_provider}"

    count = _count_questions_in_native(result_txt)
    return result_txt, count, used_provider
