"""Sample answer generation for interview questions (one best answer per question)."""
from __future__ import annotations

import json
import re

from INTERVIEW.generation_utils import (
    _parse_llm_json_object,
    resolve_ollama_model_name,
    track_token_usage,
    try_ollama_chat,
)

# Bedrock Converse override is capped at 8192 in common/llm/bedrock.py
ANSWER_BATCH_MAX_TOKENS = 8192
ANSWER_BATCH_TEMPERATURE = 0.3
ANSWER_BATCH_MAX_RETRIES = 3
ANSWER_BATCH_CHUNK_SIZE = 8  # keep room for long / coding answers
DOSSIER_ANSWER_MAX_CHARS = 9000
MIN_ANSWER_CHARS = 80


def _compact_dossier_for_answers(dossier: dict | None) -> str:
    """Serialize dossier for the answer prompt, trimmed if oversized."""
    payload = dossier if isinstance(dossier, dict) else {}
    compact = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if len(compact) <= DOSSIER_ANSWER_MAX_CHARS:
        return compact
    slim = {
        "job_title": payload.get("job_title"),
        "hiring_company": payload.get("hiring_company"),
        "seniority": payload.get("seniority"),
        "domain": payload.get("domain"),
        "must_have_skills": (payload.get("must_have_skills") or [])[:8],
        "jd_highlights": (payload.get("jd_highlights") or [])[:8],
        "overlap_skills": (payload.get("overlap_skills") or [])[:10],
        "gap_skills": (payload.get("gap_skills") or [])[:8],
        "transferable_bridges": (payload.get("transferable_bridges") or [])[:6],
        "resume_anchors": (payload.get("resume_anchors") or [])[:8],
        "experience": (payload.get("experience") or [])[:5],
        "projects": (payload.get("projects") or [])[:5],
        "resume_highlights": (payload.get("resume_highlights") or [])[:5],
    }
    return json.dumps(slim, separators=(",", ":"), ensure_ascii=False)[:DOSSIER_ANSWER_MAX_CHARS]


def _normalize_level(raw_level) -> str:
    level = (raw_level or "medium").strip().lower()
    if level in ("easy", "beginner", "basic"):
        return "easy"
    if level in ("hard", "expert", "advanced"):
        return "hard"
    # coding questions map to medium difficulty but keep requires_code
    return "medium"


def _dedupe_question_rows(question_rows: list) -> list[dict]:
    """One canonical row per (difficulty_level, question_text). Prefer earliest id."""
    seen = set()
    unique = []
    for row in question_rows or []:
        q_text = (row.get("question_text") or row.get("question") or "").strip()
        if not q_text:
            continue
        raw_level = str(row.get("difficulty_level") or row.get("difficulty_category") or "").strip().lower()
        level = _normalize_level(raw_level)
        key = (level, q_text.lower())
        if key in seen:
            continue
        seen.add(key)
        requires_code = row.get("requires_code", False)
        if isinstance(requires_code, str):
            requires_code = requires_code.lower() == "true"
        if raw_level == "coding":
            requires_code = True
        existing_answer = row.get("expected_answer") or row.get("answer") or ""
        unique.append({
            "id": str(row.get("id") or ""),
            "question_text": q_text,
            "difficulty_level": level,
            "requires_code": bool(requires_code),
            "question_set": row.get("question_set"),
            "resume_id": row.get("resume_id"),
            "jd_id": row.get("jd_id"),
            "expected_answer": str(existing_answer).strip(),
        })
    return unique


def _chunk_questions(questions: list[dict]) -> list[list[dict]]:
    """Split into chunks; put coding questions in smaller chunks for full solutions."""
    if not questions:
        return []
    coding = [q for q in questions if q.get("requires_code")]
    other = [q for q in questions if not q.get("requires_code")]
    chunks: list[list[dict]] = []

    coding_chunk_size = max(3, ANSWER_BATCH_CHUNK_SIZE // 2)
    for i in range(0, len(coding), coding_chunk_size):
        chunks.append(coding[i : i + coding_chunk_size])
    for i in range(0, len(other), ANSWER_BATCH_CHUNK_SIZE):
        chunks.append(other[i : i + ANSWER_BATCH_CHUNK_SIZE])
    return chunks


def _build_answer_batch_prompt(
    dossier: dict,
    questions: list[dict],
    job_title: str = "",
    missing_ids: list[str] | None = None,
) -> str:
    title = (job_title or (dossier or {}).get("job_title") or "the role").strip()
    dossier_blob = _compact_dossier_for_answers(dossier)
    q_lines = []
    for q in questions:
        qid = q["id"]
        level = q.get("difficulty_level") or "medium"
        code_flag = " requires_code=true" if q.get("requires_code") else ""
        text = q["question_text"]
        q_lines.append(f'- id="{qid}" level={level}{code_flag}: {text}')
    questions_block = "\n".join(q_lines)

    repair = ""
    if missing_ids:
        repair = (
            "\n\nIMPORTANT: Previous response missed these question ids: "
            + ", ".join(missing_ids)
            + ". Return a COMPLETE JSON object with every id listed above — "
            "especially the missing ones. Do not omit any."
        )

    return f"""You are an expert interview coach writing ONE strong sample answer per question for a candidate preparing for **{title}**.

CANDIDATE + ROLE DOSSIER (use this as ground truth; do not invent employers/projects/skills not present):
{dossier_blob}

QUESTIONS:
{questions_block}

Rules:
- Return ONLY one JSON object. Keys must be the question id strings. Values are answer strings.
- Exactly one best sample answer per question (not easy/intermediate/expert variants).
- Answers must be FULL interview-prep quality — not brief blurbs. Cover approach, reasoning, tools/tech, and a concrete example from the dossier when relevant.
- For requires_code=true questions: include a COMPLETE working solution (full code), plus a short explanation of approach and complexity. Do not truncate mid-function.
- You may put code inside the answer string using markdown fences (```language ... ```).
- Match depth to level: easy = clear and complete; medium = practical depth; hard = tradeoffs and judgment.
- Ground answers in the dossier (anchors, highlights, bridges) when relevant. Do not invent employers/projects.
- Every question id in the list MUST appear as a key. No missing keys.
- No commentary outside the JSON object.

Example shape:
{{"uuid-1": "Full sample answer with enough detail for interview prep...", "uuid-2": "..."}}
{repair}
"""


def _extract_answers_map(raw: str, question_ids: list[str]) -> dict[str, str]:
    """Parse LLM JSON into id -> answer. Accepts answers array fallback."""
    parsed = _parse_llm_json_object(raw)
    out: dict[str, str] = {}

    if isinstance(parsed, dict):
        for qid in question_ids:
            val = parsed.get(qid)
            if isinstance(val, str) and val.strip():
                out[qid] = val.strip()
            elif isinstance(val, dict):
                ans = val.get("answer") or val.get("expected_answer") or val.get("sample_answer")
                if isinstance(ans, str) and ans.strip():
                    out[qid] = ans.strip()

        if not out and isinstance(parsed.get("answers"), dict):
            for qid in question_ids:
                val = parsed["answers"].get(qid)
                if isinstance(val, str) and val.strip():
                    out[qid] = val.strip()
        if not out and isinstance(parsed.get("answers"), list):
            for item in parsed["answers"]:
                if not isinstance(item, dict):
                    continue
                qid = str(item.get("id") or item.get("question_id") or "")
                ans = item.get("answer") or item.get("expected_answer") or item.get("sample_answer")
                if qid in question_ids and isinstance(ans, str) and ans.strip():
                    out[qid] = ans.strip()

    if out:
        return out

    for qid in question_ids:
        pattern = rf'"{re.escape(qid)}"\s*:\s*"((?:\\.|[^"\\])*)"'
        m = re.search(pattern, raw or "", flags=re.DOTALL)
        if m:
            try:
                out[qid] = json.loads(f'"{m.group(1)}"').strip()
            except Exception:
                out[qid] = m.group(1).replace('\\"', '"').strip()
    return out


def _is_usable_answer(answer: str, requires_code: bool = False) -> bool:
    text = (answer or "").strip()
    if len(text) < MIN_ANSWER_CHARS:
        return False
    if requires_code:
        # Prefer real code blocks; still accept long plain-code answers
        has_fence = "```" in text
        has_codey = any(
            token in text
            for token in ("def ", "function ", "class ", "SELECT ", "const ", "import ", "public ")
        )
        if not has_fence and not has_codey:
            return False
        if has_fence and text.count("```") < 2:
            return False  # truncated fence
    return True


def rows_needing_answers(question_rows: list) -> list[dict]:
    """Canonical rows that still lack a usable sample answer."""
    needing = []
    for q in _dedupe_question_rows(question_rows):
        answer = q.get("expected_answer") or q.get("answer") or ""
        if not _is_usable_answer(answer, requires_code=bool(q.get("requires_code"))):
            needing.append(q)
    return needing


def _call_chunk_until_complete(
    dossier: dict,
    chunk: list[dict],
    model: str,
    job_title: str,
    dossier_cache: str,
    chunk_index: int,
    chunk_total: int,
) -> tuple[dict[str, str], str | None]:
    """LLM call(s) for one chunk until all ids have usable answers, or retries exhausted."""
    question_ids = [q["id"] for q in chunk]
    by_id = {q["id"]: q for q in chunk}
    answers_map: dict[str, str] = {}
    last_error = None
    missing = list(question_ids)

    for attempt in range(ANSWER_BATCH_MAX_RETRIES):
        prompt = _build_answer_batch_prompt(
            dossier,
            chunk if attempt == 0 else [by_id[i] for i in missing],
            job_title=job_title,
            missing_ids=missing if attempt > 0 else None,
        )
        target_ids = missing if attempt > 0 else question_ids
        try:
            print(
                f"[INFO] Answer batch LLM chunk {chunk_index}/{chunk_total} "
                f"attempt {attempt + 1}/{ANSWER_BATCH_MAX_RETRIES} "
                f"questions={len(target_ids)} max_tokens={ANSWER_BATCH_MAX_TOKENS} "
                f"dossier_cache={dossier_cache}"
            )
            response = try_ollama_chat(
                prompt.strip(),
                model=model,
                max_tokens=ANSWER_BATCH_MAX_TOKENS,
                temperature=ANSWER_BATCH_TEMPERATURE,
            )
            raw = (response.get("message") or {}).get("content") or ""
            parsed = _extract_answers_map(raw, target_ids)
            for qid, ans in parsed.items():
                if _is_usable_answer(ans, requires_code=bool(by_id.get(qid, {}).get("requires_code"))):
                    answers_map[qid] = ans
            missing = [qid for qid in question_ids if qid not in answers_map]
            print(
                f"[INFO] Answer batch chunk {chunk_index}/{chunk_total} "
                f"answers={len(answers_map)}/{len(question_ids)} missing={len(missing)}"
            )
            if not missing:
                return answers_map, None
            last_error = "incomplete_or_weak_answers"
        except Exception as exc:
            last_error = str(exc)
            print(
                f"[WARN] Answer batch chunk {chunk_index}/{chunk_total} "
                f"attempt {attempt + 1} failed: {exc}"
            )

    return answers_map, last_error or "incomplete_answers"


def generate_sample_answers_batch(
    dossier: dict,
    question_rows: list,
    model: str = "llama3",
    job_title: str = "",
    dossier_cache: str = "hit",
):
    """
    Generate one best sample answer per unique question via chunked LLM calls.
    No template fallbacks. Succeeded answers are returned even if some ids fail;
    callers should save those and retry only the missing questions.
    """
    resolved_model = resolve_ollama_model_name(model)
    unique = _dedupe_question_rows(question_rows)
    if not unique:
        return {"success": False, "error": "No questions found to generate answers for"}
    if not isinstance(dossier, dict) or not dossier:
        return {
            "success": False,
            "error": "Interview dossier not found for this resume and job description",
        }

    for i, q in enumerate(unique):
        if not q.get("id"):
            q["id"] = f"q{i + 1}"

    chunks = _chunk_questions(unique)
    answers_map: dict[str, str] = {}
    last_error = None

    print(
        f"[INFO] Answer generation start: questions={len(unique)} chunks={len(chunks)} "
        f"max_tokens={ANSWER_BATCH_MAX_TOKENS} chunk_size={ANSWER_BATCH_CHUNK_SIZE} "
        f"dossier_cache={dossier_cache}"
    )

    with track_token_usage(label="answer_generation") as token_tracker:
        for idx, chunk in enumerate(chunks, start=1):
            chunk_answers, err = _call_chunk_until_complete(
                dossier=dossier,
                chunk=chunk,
                model=resolved_model,
                job_title=job_title,
                dossier_cache=dossier_cache,
                chunk_index=idx,
                chunk_total=len(chunks),
            )
            answers_map.update(chunk_answers)
            if err:
                last_error = err
        token_usage = token_tracker.as_dict()
        token_tracker.log(
            extra=(
                f"dossier_cache={dossier_cache} questions={len(unique)} "
                f"chunks={len(chunks)}"
            )
        )

    missing = []
    enriched = []
    for q in unique:
        qid = q["id"]
        ans = (answers_map.get(qid) or "").strip()
        if not _is_usable_answer(ans, requires_code=bool(q.get("requires_code"))):
            missing.append(qid)
            continue
        enriched.append({
            **q,
            "expected_answer": ans,
            "answer": ans,
            "answer_source": "ai",
            "difficulty_category": q.get("difficulty_level"),
        })

    stats = {
        "requested": True,
        "model": resolved_model,
        "generated_count": len(enriched),
        "requested_count": len(unique),
        "fallback_count": 0,
        "fallback_examples": [],
        "missing_ids": missing,
        "llm_calls": token_usage.get("llm_calls", 0),
        "input_tokens": token_usage.get("input_tokens", 0),
        "output_tokens": token_usage.get("output_tokens", 0),
        "total_tokens": token_usage.get("total_tokens", 0),
        "dossier_cache": dossier_cache,
        "batch": True,
        "chunks": len(chunks),
        "answers_per_question": 1,
        "last_error": last_error,
    }

    if missing:
        print(
            f"[ERROR] Answer generation incomplete: missing={len(missing)}/{len(unique)} "
            f"saved={len(enriched)} ids={missing[:5]}{'...' if len(missing) > 5 else ''}"
        )
        return {
            "success": bool(enriched),
            "partial": bool(enriched),
            "error": (
                f"LLM did not return complete sample answers for {len(missing)} question(s). "
                "Please try again."
            ),
            "questions": enriched,
            "questions_count": len(enriched),
            "answer_generation": stats,
            "ollama_model": resolved_model,
        }

    print(
        f"[DONE] Sample answers ready: ai={len(enriched)} fallback=0 "
        f"total={len(enriched)} chunks={len(chunks)} dossier_cache={dossier_cache}"
    )
    return {
        "success": True,
        "partial": False,
        "questions": enriched,
        "questions_count": len(enriched),
        "answer_generation": stats,
        "ollama_model": resolved_model,
    }


def run_generate_answers_for_question_set(
    dossier,
    question_rows,
    model="llama3",
    job_title="",
    dossier_cache="hit",
    **_unused,
):
    """
    Generate one sample answer per question using the interview dossier.
    Chunked LLM calls; no template fallbacks.
    """
    return generate_sample_answers_batch(
        dossier=dossier,
        question_rows=question_rows,
        model=model,
        job_title=job_title,
        dossier_cache=dossier_cache,
    )
