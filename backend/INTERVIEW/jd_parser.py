"""Job description file/URL parsing and technical-role classification."""
from __future__ import annotations

import json
import os
import re

import requests
from html import unescape as html_unescape

from INTERVIEW.Resumeparser import extract_text_from_resume
from INTERVIEW.generation_utils import resolve_ollama_model_name, try_ollama_chat


def parse_job_description_file(file_path, model="llama3"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        full_text = extract_text_from_resume(file_path)
        if not full_text or not full_text.strip():
            raise RuntimeError(
                "No text could be extracted from the job description file. "
                "It may be image-only (scanned PDF). Use a file with selectable text, "
                "or install Tesseract-OCR and add it to PATH."
            )
    except (ValueError, FileNotFoundError):
        raise
    except Exception as e:
        raise RuntimeError(f"Text extraction failed: {e}")
 
    # Token-based chunking
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(full_text)
    max_tokens = 1500
    overlap = 200

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk = enc.decode(tokens[start:end])
        chunks.append(chunk)
        start += max_tokens - overlap

    print(f"[INFO] JD token count: {len(tokens)}; Total Chunks: {len(chunks)}")

    result = {
        "job_title": "",
        "job_description": ""
    }

    for idx, chunk in enumerate(chunks):
        print(f"[INFO] Parsing JD chunk {idx+1}/{len(chunks)}")

        prompt = f"""
        You are an intelligent AI assistant. Extract a structured **job title** and **complete job description summary** from the following job description chunk.

        Job title should be a concise label (e.g., "Product Manager").

        Job description should:
        - Include purpose, responsibilities, required skills, education, tools, and expectations
        - Be written as a clean paragraph (not a list)
        - Include only what's mentioned in the chunk
        - Avoid repetition or vague filler

        Return JSON:
        {{
        "job_title": "...",
        "job_description": "..."
        }}

        Job Description Chunk:
        \"\"\"{chunk}\"\"\"
        """

        try:
            response = try_ollama_chat(prompt.strip(), model=model)
            raw = response["message"]["content"]

            try:
                parsed = json.loads(raw)
            except:
                match = re.search(r'\{[\s\S]*\}', raw)
                if match:
                    parsed = json.loads(match.group(0))
                else:
                    print(f"[WARNING] Skipping chunk {idx+1} due to parse failure.")
                    continue

            # Set job title once (if not yet filled)
            if not result["job_title"] and parsed.get("job_title"):
                result["job_title"] = parsed["job_title"]

            # Append description
            desc = parsed.get("job_description", "").strip()
            if desc and desc not in result["job_description"]:
                result["job_description"] += " " + desc

        except Exception as e:
            print(f"[ERROR] Failed to process chunk {idx+1}: {e}")
            continue

    result["job_description"] = result["job_description"].strip()
    return result


def _html_to_structured_text(html: str) -> str:
    """Convert HTML to plain text while preserving headings, lists, and paragraph breaks."""
    if not html:
        return ""

    cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<br\s*/?>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r'</?(?:p|div|section|article|header|footer|main|blockquote|h[1-6]|tr)\b[^>]*>',
        '\n',
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r'<li[^>]*>', '\n- ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</li>', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'</?(?:ul|ol|table|tbody|thead)\b[^>]*>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = html_unescape(cleaned)

    lines: list[str] = []
    for line in cleaned.splitlines():
        normalized = re.sub(r'[ \t]+', ' ', line).strip()
        if normalized:
            lines.append(normalized)
        elif lines and lines[-1] != '':
            lines.append('')

    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def _extract_visible_text_from_html(html: str, max_chars: int = 20000) -> str:
    """Lightweight HTML → text converter without external dependencies."""
    text = _html_to_structured_text(html)
    if not text:
        return ""
    if max_chars:
        text = text[:max_chars]
    return text


def _coarse_plain_text_from_html(html: str, max_chars: int = 28000) -> str:
    """Strip tags to plain text when visible-text extraction yields little."""
    text = _html_to_structured_text(html or '')
    if max_chars:
        text = text[:max_chars]
    return text


_MAX_JD_URL_PAGE_CHARS = 28000
_LLM_JOB_URL_RETRIES = 3
JD_URL_MANUAL_PASTE_MESSAGE = (
     "We couldn't fetch the job description from this link. "
     "Please paste it manually in the 'Paste Description' tab."
)


def _parse_llm_job_extraction_response(raw: str):
    """Parse JSON object from model output; tolerate extra prose around JSON."""
    text = (raw or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        return json.loads(match.group(0)) if match else None


def _llm_extract_job_from_page_content(page_plain_text: str, page_url: str, model: str) -> dict:
    """Use Ollama to extract job_title and job_description from page text."""
    prompt = f"""You extract structured data from noisy web page text (often from a job board).

Source URL (context only): {page_url}

Page text:
\"\"\"
{page_plain_text}
\"\"\"

Identify the primary job posting on this page. Return one JSON object with exactly these keys:
- "job_title": string — the role name as shown on the posting; "" if unknown.
- "job_description": string — the full job description: summary, responsibilities, requirements, qualifications, and benefits that belong to this role. Preserve structure with section headings on their own lines (e.g. Responsibilities, Requirements), each bullet on its own line starting with "- ", and blank lines between sections. Plain text only (no markdown code fences or **bold**); "" if not present.
- "requires_manual_paste": boolean — true only if there is no usable job description (login wall, empty shell, mostly JavaScript boilerplate, or wrong page).

Rules:
- Use only what appears in the page text; do not invent duties or skills.
- Omit navigation, cookie banners, footers, "similar jobs", and generic apply/sign-in chrome from the description.
- Keep the posting's readable layout: headings, bullet lists, and paragraph breaks using newlines.
- Output only valid JSON. No markdown code fences, no commentary before or after.

JSON:"""

    last_error = None
    for attempt in range(_LLM_JOB_URL_RETRIES):
        try:
            response = try_ollama_chat(prompt, model=model)
            raw = response["message"]["content"]
            parsed = _parse_llm_job_extraction_response(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Model did not return a JSON object")
            title = parsed.get("job_title")
            desc = parsed.get("job_description")
            manual = parsed.get("requires_manual_paste")
            if not isinstance(title, str):
                title = str(title) if title is not None else ""
            if not isinstance(desc, str):
                desc = str(desc) if desc is not None else ""
            return {
                "job_title": title.strip(),
                "job_description": desc.strip(),
                "requires_manual_paste": bool(manual),
            }
        except Exception as e:
            last_error = e
            print(f"[WARNING] LLM job URL extraction attempt {attempt + 1}/{_LLM_JOB_URL_RETRIES} failed: {e}")
    raise RuntimeError(f"LLM job extraction failed after {_LLM_JOB_URL_RETRIES} attempts: {last_error}")


def extract_job_from_url(url: str, model: str = "llama3"):
    """
    Fetch a public job posting URL and extract job_title and job_description.
    """
    if not url or not isinstance(url, str):
        raise ValueError("A non-empty URL string is required")

    from urllib.parse import urlparse
    parsed_input = urlparse(url.strip())
    if parsed_input.scheme not in ("http", "https") or not parsed_input.netloc:
        raise ValueError("Please provide a valid http(s) job URL")

    resolved_model = resolve_ollama_model_name(model)

    def _try_fetch_html(target_url, headers, timeout_seconds, label):
        resp = requests.get(target_url, headers=headers, timeout=timeout_seconds, allow_redirects=True)
        status = resp.status_code
        if status >= 400 and status != 999:
            raise RuntimeError(f"{label}: upstream returned HTTP {status}")
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError(f"{label}: empty response body")
        return text

    desktop_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    mobile_headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    fetch_attempt_errors = []
    html = ""
    fallback_plan = [
        ("desktop-direct", url, desktop_headers, 20),
        ("mobile-direct", url, mobile_headers, 20),
    ]

    canonical = url.strip()
    if canonical.startswith("https://"):
        canonical = canonical[len("https://"):]
    elif canonical.startswith("http://"):
        canonical = canonical[len("http://"):]
    fallback_plan.append(
        ("reader-mirror", f"https://r.jina.ai/http://{canonical}", desktop_headers, 25)
    )

    for label, target_url, headers, timeout_seconds in fallback_plan:
        try:
            html = _try_fetch_html(target_url, headers, timeout_seconds, label)
            print(f"[INFO] JD URL fetch succeeded via: {label}")
            break
        except requests.exceptions.RequestException as e:
            fetch_attempt_errors.append(f"{label}: {e}")
            continue
        except Exception as e:
            fetch_attempt_errors.append(f"{label}: {e}")
            continue

    if not html:
        raise RuntimeError(
            "Failed to fetch URL with fallback strategies: " + " | ".join(fetch_attempt_errors)
        )

    visible = _extract_visible_text_from_html(html, max_chars=_MAX_JD_URL_PAGE_CHARS)
    coarse = _coarse_plain_text_from_html(html, _MAX_JD_URL_PAGE_CHARS)
    page_plain = (visible or coarse)[:_MAX_JD_URL_PAGE_CHARS]

    llm_result = _llm_extract_job_from_page_content(page_plain, url.strip(), resolved_model)

    requires_manual_paste = bool(llm_result.get("requires_manual_paste"))
    warning_message = JD_URL_MANUAL_PASTE_MESSAGE if requires_manual_paste else ""

    return {
        "job_title": llm_result.get("job_title", "").strip(),
        "job_description": llm_result.get("job_description", "").strip(),
        "job_responsibilities": "",
        "requires_manual_paste": requires_manual_paste,
        "warning_message": warning_message,
    }


def _keyword_classify_technical_role(job_title, job_description):
    from common.role_classification import classify_job_description_is_technical
    return classify_job_description_is_technical(job_title, job_description)


def _parse_technical_flag(raw: str):
    """
    Extract is_technical from model output.
    Returns True/False on success, None if unparseable.
    """
    from INTERVIEW.generation_utils import (
        _parse_llm_json_object,
        _strip_markdown_json_fence,
        clean_json_like_text,
    )

    text = (raw or "").strip()
    if not text:
        return None

    candidates = [
        text,
        _strip_markdown_json_fence(text),
        clean_json_like_text(_strip_markdown_json_fence(text)),
    ]
    for candidate in candidates:
        parsed = _parse_llm_json_object(candidate)
        if isinstance(parsed, dict) and "is_technical" in parsed:
            value = parsed.get("is_technical")
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "1"}:
                    return True
                if lowered in {"false", "no", "0"}:
                    return False
            if isinstance(value, (int, float)):
                return bool(value)

    # Bare true/false (or yes/no) somewhere in the reply
    match = re.search(r"\b(true|false|yes|no)\b", text, re.IGNORECASE)
    if match:
        token = match.group(1).lower()
        return token in {"true", "yes"}

    return None


def classify_if_technical_role(job_title, job_description, model="llama3"):
    """
    Returns True if the job description implies that
    technical/coding questions can be asked.
    Returns False otherwise.
    """
    title = (job_title or "").strip()
    description = (job_description or "").strip()
    # Keep prompt small so the model reliably returns a short JSON object.
    description_excerpt = description[:2500]
    if len(description) > 2500:
        description_excerpt += "\n...[truncated]..."

    keyword_result = _keyword_classify_technical_role(title, description)

    prompt = f"""Classify whether this role expects coding/programming interview questions.

Job title: {title}

Job description (excerpt):
\"\"\"{description_excerpt}\"\"\"

Return ONLY this JSON object (no markdown, no other text):
{{"is_technical": true}}
or
{{"is_technical": false}}

Rules:
- true: software/dev/data/QA automation/devops/SRE/ML eng or coding languages are required.
- false: non-coding roles (HR, sales, pure PM, support without scripting).
- If unsure, prefer true only when coding duties are clearly present.
"""

    try:
        response = try_ollama_chat(prompt.strip(), model=model)
        raw = ((response or {}).get("message") or {}).get("content") or ""
    except Exception as llm_error:
        print(f"[WARN] LLM technical classification call failed, using keyword fallback: {llm_error}")
        return keyword_result

    parsed = _parse_technical_flag(raw)
    if parsed is not None:
        return parsed

    snippet = (raw or "").strip().replace("\n", " ")[:120]
    if snippet:
        print(
            "[WARN] LLM technical classification unusable output "
            f"(len={len(raw)}); using keyword fallback. snippet={snippet!r}"
        )
    else:
        print("[WARN] LLM technical classification returned empty content; using keyword fallback.")
    return keyword_result

