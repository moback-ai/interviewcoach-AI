"""Interview dossier + question generation (core/split/blend/hybrid/coding) + API pipeline."""
from __future__ import annotations

import json
import os
import re

from colorama import Fore, Style, init

init(autoreset=True)

from INTERVIEW.generation_utils import (
    ResumeParseError,
    _parse_llm_json_object,
    extract_json_array,
    read_questions_from_csv,
    resolve_ollama_model_name,
    save_json_output,
    save_questions_to_csv,
    track_token_usage,
    try_ollama_chat,
)
from INTERVIEW.Resumeparser import (
    build_structured_data_from_skills,
    extract_text_from_resume,
)
from INTERVIEW.dossier_store import load_dossier, save_dossier


QUESTION_GEN_MAX_RETRIES = 3
DOSSIER_LLM_MAX_RETRIES = 8
DOSSIER_LLM_MAX_TOKENS = 3072
DOSSIER_LLM_TEMPERATURE = 0.2
DOSSIER_TARGET_MAX_CHARS = 4500
JD_PREP_EXCERPT_MAX = 3000
RESUME_PREP_DESC_MAX = 160
RESUME_TEXT_DOSSIER_MAX = 10000
QUESTION_REPAIR_MAX_PASSES = 1


def _candidate_name_from_text(resume_text: str) -> str:
    """Light non-LLM name guess from the first resume line."""
    lines = [line.strip() for line in (resume_text or "").splitlines() if line.strip()]
    name = lines[0][:80] if lines else "candidate"
    if len(name.split()) > 5:
        name = "candidate"
    safe = re.sub(r"[^\w\-]+", "_", name).strip("_") or "candidate"
    return safe[:60]


def _stub_structured_from_dossier(dossier: dict, candidate_name: str, skills_list=None) -> dict:
    """Minimal stub so question generators do not rebuild the dossier."""
    skills = list(skills_list or [])[:25]
    if not skills:
        skills = list((dossier or {}).get("resume_skills") or [])[:25]
    return {
        "name": (candidate_name or "candidate").replace("_", " "),
        "skills": skills,
        "work_experience": list((dossier or {}).get("experience") or [])[:5],
        "projects": list((dossier or {}).get("projects") or [])[:5],
        "summary": "",
        "companies": list((dossier or {}).get("companies") or [])[:5],
        "parse_source": "dossier_stub",
    }


def _shorten_text(text, max_chars):
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _normalize_skill_token(token):
    if not isinstance(token, str):
        return ""
    t = token.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _dedupe_str_list(items, limit=40):
    seen = set()
    out = []
    for s in items or []:
        if not isinstance(s, str):
            continue
        s = s.strip()
        key = _normalize_skill_token(s)
        if key and key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= limit:
            break
    return out


def _collect_resume_skills(structured_resume):
    """Pull skills/tools already present on the parsed resume (truncation only, not invented)."""
    skills = []
    for s in structured_resume.get("skills") or []:
        if isinstance(s, str) and s.strip():
            skills.append(s.strip())

    tools = structured_resume.get("tools_and_technologies") or {}
    if isinstance(tools, dict):
        for values in tools.values():
            if isinstance(values, list):
                for v in values:
                    if isinstance(v, str) and v.strip():
                        skills.append(v.strip())
            elif isinstance(values, str) and values.strip():
                skills.append(values.strip())

    for project in structured_resume.get("projects") or []:
        if not isinstance(project, dict):
            continue
        proj_tools = project.get("tools") or []
        if isinstance(proj_tools, list):
            for t in proj_tools:
                if isinstance(t, str) and t.strip():
                    skills.append(t.strip())
        elif isinstance(proj_tools, str) and proj_tools.strip():
            skills.extend([p.strip() for p in proj_tools.split(",") if p.strip()])

    return _dedupe_str_list(skills, limit=40)


def _build_resume_prep_slice(structured_resume):
    """
    Token-control truncation of already-parsed resume JSON for the Bedrock dossier call.
    Does not invent employers, skills, or projects.
    """
    structured_resume = structured_resume or {}
    experiences = []
    for exp in (structured_resume.get("work_experience") or [])[:5]:
        if not isinstance(exp, dict):
            continue
        item = {
            "title": _shorten_text(exp.get("title") or "", 60),
            "company": _shorten_text(exp.get("company") or "", 40),
            "description": _shorten_text(exp.get("description") or "", RESUME_PREP_DESC_MAX),
        }
        if item["title"] or item["company"] or item["description"]:
            experiences.append(item)

    projects = []
    for proj in (structured_resume.get("projects") or [])[:5]:
        if not isinstance(proj, dict):
            continue
        tools = proj.get("tools") or []
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        elif not isinstance(tools, list):
            tools = []
        item = {
            "name": _shorten_text(proj.get("name") or "", 50),
            "role": _shorten_text(proj.get("role") or "", 40),
            "tools": [str(t) for t in tools[:6] if t],
            "description": _shorten_text(proj.get("description") or "", RESUME_PREP_DESC_MAX),
        }
        if item["name"] or item["description"]:
            projects.append(item)

    return {
        "name": _shorten_text(structured_resume.get("name") or "", 60),
        "summary": _shorten_text(structured_resume.get("summary") or "", 220),
        "skills": _collect_resume_skills(structured_resume)[:20],
        "experience": experiences[:5],
        "projects": projects[:5],
    }


def _empty_dossier(job_title, prep_slice=None, jd_excerpt="", reason="llm_failed"):
    """Hard-failure shell only — no invented JD metrics or fake quality fields."""
    prep_slice = prep_slice or {}
    return {
        "job_title": job_title or "",
        "hiring_company": "",
        "seniority": "",
        "domain": "",
        "must_have_skills": [],
        "nice_to_have_skills": [],
        "responsibilities": [],
        "tools": [],
        "resume_skills": list(prep_slice.get("skills") or [])[:20],
        "companies": [],
        "experience": list(prep_slice.get("experience") or [])[:5],
        "projects": list(prep_slice.get("projects") or [])[:5],
        "resume_highlights": [],
        "overlap_skills": [],
        "gap_skills": [],
        "transferable_bridges": [],
        "resume_anchors": [],
        "jd_excerpt": _shorten_text(jd_excerpt or "", 600),
        "source": reason,
    }


def _coerce_str_list(value, limit=12, item_max=140):
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(_shorten_text(item.strip(), item_max))
        elif isinstance(item, dict):
            # allow highlight objects -> compact string
            parts = [
                str(item.get(k)).strip()
                for k in ("company", "title", "name", "role", "project", "description", "bridge")
                if item.get(k)
            ]
            if parts:
                out.append(_shorten_text(" | ".join(parts), item_max))
        if len(out) >= limit:
            break
    return out


def _coerce_experience_list(value, limit=5):
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append({
                "company": "",
                "title": "",
                "dates": "",
                "tech": [],
                "description": _shorten_text(item.strip(), RESUME_PREP_DESC_MAX),
            })
        elif isinstance(item, dict):
            tech = item.get("tech") or item.get("tools") or []
            if isinstance(tech, str):
                tech = [t.strip() for t in tech.split(",") if t.strip()]
            elif not isinstance(tech, list):
                tech = []
            exp = {
                "company": _shorten_text(str(item.get("company") or ""), 50),
                "title": _shorten_text(str(item.get("title") or item.get("role") or ""), 60),
                "dates": _shorten_text(str(item.get("dates") or item.get("duration") or ""), 40),
                "tech": _coerce_str_list(tech, limit=8, item_max=40),
                "description": _shorten_text(
                    str(item.get("description") or item.get("summary") or ""),
                    RESUME_PREP_DESC_MAX,
                ),
            }
            if exp["company"] or exp["title"] or exp["description"]:
                out.append(exp)
        if len(out) >= limit:
            break
    return out


def _coerce_project_list(value, limit=5):
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append({
                "name": _shorten_text(item.strip(), 60),
                "role": "",
                "tech": [],
                "description": "",
            })
        elif isinstance(item, dict):
            tech = item.get("tech") or item.get("tools") or []
            if isinstance(tech, str):
                tech = [t.strip() for t in tech.split(",") if t.strip()]
            elif not isinstance(tech, list):
                tech = []
            proj = {
                "name": _shorten_text(str(item.get("name") or item.get("project") or ""), 60),
                "role": _shorten_text(str(item.get("role") or ""), 40),
                "tech": _coerce_str_list(tech, limit=8, item_max=40),
                "description": _shorten_text(
                    str(item.get("description") or item.get("summary") or ""),
                    RESUME_PREP_DESC_MAX,
                ),
            }
            if proj["name"] or proj["description"]:
                out.append(proj)
        if len(out) >= limit:
            break
    return out


def _coerce_resume_anchors(value, limit=10):
    """Prefer rich objects; fall back to strings for older caches / thin LLM output."""
    out = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(_shorten_text(item.strip(), 80))
        elif isinstance(item, dict):
            tech = item.get("tech") or item.get("tools") or []
            if isinstance(tech, str):
                tech = [t.strip() for t in tech.split(",") if t.strip()]
            elif not isinstance(tech, list):
                tech = []
            actions = item.get("actions") or []
            if isinstance(actions, str):
                actions = [actions.strip()] if actions.strip() else []
            elif not isinstance(actions, list):
                actions = []
            anchor = {
                "company": _shorten_text(str(item.get("company") or ""), 50),
                "project": _shorten_text(
                    str(item.get("project") or item.get("name") or ""), 60
                ),
                "tech": _coerce_str_list(tech, limit=6, item_max=40),
                "actions": _coerce_str_list(actions, limit=4, item_max=80),
            }
            if anchor["company"] or anchor["project"] or anchor["tech"] or anchor["actions"]:
                out.append(anchor)
        if len(out) >= limit:
            break
    return out


def _dossier_grounding_ok(dossier: dict) -> bool:
    """True when dossier has enough resume grounding for quality question gen."""
    if not isinstance(dossier, dict):
        return False
    has_exp = bool(dossier.get("experience"))
    has_proj = bool(dossier.get("projects"))
    has_companies = bool(dossier.get("companies"))
    has_anchors = bool(dossier.get("resume_anchors"))
    has_skills = bool(dossier.get("resume_skills") or dossier.get("must_have_skills"))
    return (has_exp or has_proj or has_companies or has_anchors) and has_skills


def _log_dossier_field_counts(dossier: dict, prefix: str = "[INFO]") -> None:
    d = dossier or {}
    print(
        f"{prefix} Dossier fields: "
        f"companies={len(d.get('companies') or [])} "
        f"experience={len(d.get('experience') or [])} "
        f"projects={len(d.get('projects') or [])} "
        f"anchors={len(d.get('resume_anchors') or [])} "
        f"resume_skills={len(d.get('resume_skills') or [])} "
        f"overlap={len(d.get('overlap_skills') or [])} "
        f"gaps={len(d.get('gap_skills') or [])} "
        f"bridges={len(d.get('transferable_bridges') or [])} "
        f"hiring_company={d.get('hiring_company') or '-'} "
        f"source={d.get('source') or '-'}"
    )


def _shrink_dossier_to_target(dossier):
    compact = json.dumps(dossier, separators=(",", ":"))
    if len(compact) <= DOSSIER_TARGET_MAX_CHARS:
        return dossier, compact
    for e in dossier.get("experience") or []:
        if isinstance(e, dict):
            e["description"] = _shorten_text(e.get("description") or "", 80)
            e["tech"] = (e.get("tech") or [])[:4]
    for p in dossier.get("projects") or []:
        if isinstance(p, dict):
            p["description"] = _shorten_text(p.get("description") or "", 80)
            p["tech"] = (p.get("tech") or [])[:4]
    for a in dossier.get("resume_anchors") or []:
        if isinstance(a, dict):
            a["actions"] = (a.get("actions") or [])[:2]
            a["tech"] = (a.get("tech") or [])[:4]
    dossier["jd_excerpt"] = _shorten_text(dossier.get("jd_excerpt") or "", 300)
    dossier["resume_skills"] = (dossier.get("resume_skills") or [])[:12]
    dossier["resume_highlights"] = (dossier.get("resume_highlights") or [])[:5]
    dossier["responsibilities"] = (dossier.get("responsibilities") or [])[:5]
    dossier["transferable_bridges"] = (dossier.get("transferable_bridges") or [])[:5]
    compact = json.dumps(dossier, separators=(",", ":"))
    return dossier, compact


def _dossier_json_contract_block():
    """Shared LLM JSON shape for dossier builders."""
    return f"""Return ONLY one JSON object with exactly these keys:
{{
  "hiring_company": "employer from the JD if named, else empty",
  "must_have_skills": ["..."],
  "nice_to_have_skills": ["..."],
  "responsibilities": ["..."],
  "seniority": "junior|mid|senior|lead|principal|",
  "domain": "short domain label or empty",
  "tools": ["..."],
  "companies": ["past employers from the resume only"],
  "experience": [
    {{
      "company": "...",
      "title": "...",
      "dates": "optional",
      "tech": ["tools used there"],
      "description": "1-2 concrete bullets of what they did"
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "role": "optional",
      "tech": ["..."],
      "description": "what they built / owned"
    }}
  ],
  "resume_skills": ["skills explicitly present in the resume"],
  "resume_highlights": ["short highlight rooted in the resume"],
  "overlap_skills": ["skills present in BOTH resume and JD — prefer real tech, not soft skills"],
  "gap_skills": ["JD must-haves missing from the resume"],
  "transferable_bridges": [
    "short bridge e.g. 'Salesforce REST integrations -> AWS API / service integration'"
  ],
  "resume_anchors": [
    {{
      "company": "...",
      "project": "...",
      "tech": ["..."],
      "actions": ["what they did"]
    }}
  ]
}}

Rules:
- Use ONLY the provided resume/candidate text and JD text. Do not invent employers, projects, or skills.
- ALWAYS fill companies, experience, and projects when the resume mentions them (even briefly).
- Prefer precise skill/tool names over vague soft skills (do not let Agile dominate overlap_skills).
- Keep lists short: max 5 companies, 5 experience, 5 projects, 8 must_have_skills, 5 nice_to_have,
  6 responsibilities, 6 tools, 5 resume_highlights, 10 overlap_skills, 8 gap_skills,
  6 transferable_bridges, 10 resume_anchors, 20 resume_skills.
- Output a single raw JSON object only. No markdown fences. No ```json. No commentary.
- Keep descriptions short (1 sentence). Keep total JSON under ~{DOSSIER_TARGET_MAX_CHARS} characters.
"""


def _normalize_parsed_dossier(parsed, job_title, jd_excerpt, resume_skills_fallback=None, source="llm"):
    """Normalize LLM JSON into the canonical dossier shape."""
    resume_skills_fallback = resume_skills_fallback or []
    llm_resume_skills = _coerce_str_list(parsed.get("resume_skills"), limit=20, item_max=40)
    companies = _coerce_str_list(parsed.get("companies"), limit=5, item_max=50)
    experience = _coerce_experience_list(parsed.get("experience"), limit=5)
    projects = _coerce_project_list(parsed.get("projects"), limit=5)

    # Backfill companies from experience if LLM omitted the list
    if not companies and experience:
        companies = _dedupe_str_list(
            [e.get("company") for e in experience if e.get("company")],
            limit=5,
        )

    dossier = {
        "job_title": job_title,
        "hiring_company": _shorten_text(str(parsed.get("hiring_company") or ""), 50),
        "seniority": _shorten_text(str(parsed.get("seniority") or ""), 40),
        "domain": _shorten_text(str(parsed.get("domain") or ""), 40),
        "must_have_skills": _coerce_str_list(parsed.get("must_have_skills"), limit=8, item_max=40),
        "nice_to_have_skills": _coerce_str_list(parsed.get("nice_to_have_skills"), limit=5, item_max=40),
        "responsibilities": _coerce_str_list(parsed.get("responsibilities"), limit=6, item_max=140),
        "tools": _coerce_str_list(parsed.get("tools"), limit=6, item_max=40),
        "resume_skills": llm_resume_skills or list(resume_skills_fallback)[:20],
        "companies": companies,
        "experience": experience,
        "projects": projects,
        "resume_highlights": _coerce_str_list(parsed.get("resume_highlights"), limit=5, item_max=160),
        "overlap_skills": _coerce_str_list(parsed.get("overlap_skills"), limit=10, item_max=40),
        "gap_skills": _coerce_str_list(parsed.get("gap_skills"), limit=8, item_max=40),
        "transferable_bridges": _coerce_str_list(
            parsed.get("transferable_bridges"), limit=6, item_max=140
        ),
        "resume_anchors": _coerce_resume_anchors(parsed.get("resume_anchors"), limit=10),
        "jd_excerpt": _shorten_text(jd_excerpt, 600),
        "source": source,
    }
    return dossier


def _call_dossier_llm(prompt, model, label="dossier"):
    """
    Call LLM for dossier JSON with extra retries and a high output-token budget
    so rich experience/projects JSON is not truncated mid-object.
    Returns (parsed_dict|None, last_error|None, attempts_used).
    """
    parsed = None
    last_error = None
    attempts_used = 0
    print(
        f"[INFO] Dossier LLM start ({label}): up to {DOSSIER_LLM_MAX_RETRIES} attempts "
        f"max_tokens={DOSSIER_LLM_MAX_TOKENS} temperature={DOSSIER_LLM_TEMPERATURE}"
    )
    for attempt in range(DOSSIER_LLM_MAX_RETRIES):
        attempts_used = attempt + 1
        try:
            response = try_ollama_chat(
                prompt.strip(),
                model=model,
                max_tokens=DOSSIER_LLM_MAX_TOKENS,
                temperature=DOSSIER_LLM_TEMPERATURE,
            )
            raw = (response.get("message") or {}).get("content") or ""
            usage = response.get("usage") or {}
            out_tok = usage.get("output_tokens")
            parsed = _parse_llm_json_object(raw)
            if isinstance(parsed, dict) and parsed:
                print(
                    f"[INFO] Dossier LLM JSON ok ({label}) "
                    f"attempt {attempts_used}/{DOSSIER_LLM_MAX_RETRIES} "
                    f"keys={len(parsed)}"
                    + (f" output_tokens={out_tok}" if out_tok is not None else "")
                )
                return parsed, None, attempts_used
            last_error = "invalid_or_empty_json"
            preview = (raw or "").replace("\n", " ")[:180]
            print(
                f"[WARN] Dossier LLM unusable JSON ({label}) "
                f"attempt {attempts_used}/{DOSSIER_LLM_MAX_RETRIES} "
                f"raw_len={len(raw or '')} "
                + (f"output_tokens={out_tok} " if out_tok is not None else "")
                + f"preview={preview!r}"
            )
            parsed = None
        except Exception as e:
            last_error = str(e)
            print(
                f"[WARN] Dossier LLM call failed ({label}) "
                f"attempt {attempts_used}/{DOSSIER_LLM_MAX_RETRIES}: {e}"
            )
    print(
        f"[ERROR] Dossier LLM exhausted retries ({label}): "
        f"attempts={attempts_used} reason={last_error}"
    )
    return None, last_error, attempts_used


def build_interview_dossier(structured_resume, job_title, job_description, model="llama3"):
    """
    Compact JD+resume dossier for question generation via ONE Bedrock/LLM call.
    Truncation only for tokens; quality fields come from the LLM, not heuristics.
    On hard failure after capped retries: empty-ish dossier + clear log (no invented metrics).
    """
    structured_resume = structured_resume or {}
    job_title = (job_title or "").strip()
    job_description = job_description or ""
    prep_slice = _build_resume_prep_slice(structured_resume)
    jd_excerpt = _shorten_text(job_description, JD_PREP_EXCERPT_MAX)
    prep_blob = json.dumps(prep_slice, separators=(",", ":"))

    prompt = f"""You are building a rich interview dossier for question generation.

Job title: {job_title}

RESUME PREP SLICE (already parsed; do NOT invent employers, projects, or skills not listed):
{prep_blob}

JOB DESCRIPTION (truncated):
\"\"\"{jd_excerpt}\"\"\"

{_dossier_json_contract_block()}
"""

    repair_suffix = (
        "\n\nIMPORTANT: Previous output was too thin (missing companies/experience/projects/"
        "resume_anchors). Re-read the resume slice and FILL those fields from what is present. "
        "JSON only."
    )

    parsed, last_error, attempts = _call_dossier_llm(prompt, model, label="structured")
    dossier = None
    if isinstance(parsed, dict) and parsed:
        dossier = _normalize_parsed_dossier(
            parsed,
            job_title,
            jd_excerpt,
            resume_skills_fallback=prep_slice.get("skills") or [],
            source="llm",
        )
        # Prefer prep-slice experience/projects if LLM left them empty but slice has them
        if not dossier.get("experience") and prep_slice.get("experience"):
            dossier["experience"] = list(prep_slice.get("experience") or [])[:5]
        if not dossier.get("projects") and prep_slice.get("projects"):
            dossier["projects"] = list(prep_slice.get("projects") or [])[:5]
        if not dossier.get("companies") and dossier.get("experience"):
            dossier["companies"] = _dedupe_str_list(
                [e.get("company") for e in dossier["experience"] if e.get("company")],
                limit=5,
            )

        if not _dossier_grounding_ok(dossier) and attempts < DOSSIER_LLM_MAX_RETRIES:
            print(
                "[WARN] Dossier LLM output thin on resume grounding; "
                "retrying with repair prompt..."
            )
            _log_dossier_field_counts(dossier, prefix="[WARN]")
            parsed2, err2, attempts2 = _call_dossier_llm(
                prompt + repair_suffix, model, label="structured_repair"
            )
            attempts += attempts2
            if isinstance(parsed2, dict) and parsed2:
                dossier = _normalize_parsed_dossier(
                    parsed2,
                    job_title,
                    jd_excerpt,
                    resume_skills_fallback=prep_slice.get("skills") or [],
                    source="llm",
                )
            else:
                last_error = err2 or last_error

    if not isinstance(dossier, dict) or not dossier:
        print(
            f"[ERROR] Dossier LLM FAILED (structured) reason={last_error} "
            f"attempts={attempts}. Returning empty-ish dossier; no heuristic invent."
        )
        dossier = _empty_dossier(job_title, prep_slice, jd_excerpt, reason="llm_failed")
        compact = json.dumps(dossier, separators=(",", ":"))
        _log_dossier_field_counts(dossier, prefix="[ERROR]")
        print(f"[ERROR] Interview dossier ready: {len(compact)} chars (source=llm_failed)")
        return dossier

    dossier, compact = _shrink_dossier_to_target(dossier)
    grounding = "ok" if _dossier_grounding_ok(dossier) else "thin"
    print(
        f"[INFO] Dossier LLM SUCCESS (structured) attempts={attempts} "
        f"chars={len(compact)} grounding={grounding}"
    )
    _log_dossier_field_counts(dossier, prefix="[INFO]")
    return dossier


def build_interview_dossier_from_text(
    resume_text,
    job_title,
    job_description,
    model="llama3",
    skills_list=None,
):
    """
    Build interview dossier from raw resume (or skills) text + JD via ONE LLM call.
    No structured-resume parse. On hard failure: empty-ish dossier + source=llm_failed.
    """
    job_title = (job_title or "").strip()
    job_description = job_description or ""
    jd_excerpt = _shorten_text(job_description, JD_PREP_EXCERPT_MAX)

    if skills_list:
        skill_parts = [str(s).strip() for s in skills_list if str(s).strip()]
        resume_blob = "Candidate skills profile:\n" + ", ".join(skill_parts)
        resume_skills_hint = skill_parts[:20]
        label = "from_skills"
    else:
        resume_blob = _shorten_text(resume_text or "", RESUME_TEXT_DOSSIER_MAX)
        resume_skills_hint = []
        label = "from_text"

    prompt = f"""You are building a rich interview dossier for question generation.

Job title: {job_title}

RESUME / CANDIDATE TEXT (raw extract; do NOT invent employers, projects, or skills not present):
\"\"\"{resume_blob}\"\"\"

JOB DESCRIPTION (truncated):
\"\"\"{jd_excerpt}\"\"\"

Extract companies, job titles, projects, tools, and concrete actions from the resume text
into experience / projects / companies / resume_anchors. This grounding is critical.

{_dossier_json_contract_block()}
"""

    repair_suffix = (
        "\n\nIMPORTANT: Previous output was too thin (missing companies/experience/projects/"
        "resume_anchors). Scan the resume text again for employer names, project names, "
        "technologies, and what the candidate did. FILL those fields. Do not invent. JSON only."
    )

    print(f"[INFO] Building dossier via LLM ({label})...")
    parsed, last_error, attempts = _call_dossier_llm(prompt, model, label=label)
    dossier = None
    if isinstance(parsed, dict) and parsed:
        dossier = _normalize_parsed_dossier(
            parsed,
            job_title,
            jd_excerpt,
            resume_skills_fallback=resume_skills_hint,
            source="llm",
        )
        if not _dossier_grounding_ok(dossier):
            print(
                "[WARN] Dossier LLM output thin on resume grounding; "
                "retrying with repair prompt..."
            )
            _log_dossier_field_counts(dossier, prefix="[WARN]")
            parsed2, err2, attempts2 = _call_dossier_llm(
                prompt + repair_suffix, model, label=f"{label}_repair"
            )
            attempts += attempts2
            if isinstance(parsed2, dict) and parsed2:
                repaired = _normalize_parsed_dossier(
                    parsed2,
                    job_title,
                    jd_excerpt,
                    resume_skills_fallback=resume_skills_hint,
                    source="llm",
                )
                # Keep richer of the two on each grounding field
                for key in ("experience", "projects", "companies", "resume_anchors", "resume_skills"):
                    if len(repaired.get(key) or []) > len(dossier.get(key) or []):
                        dossier[key] = repaired[key]
                for key in (
                    "must_have_skills",
                    "gap_skills",
                    "overlap_skills",
                    "transferable_bridges",
                    "hiring_company",
                    "tools",
                    "responsibilities",
                    "resume_highlights",
                ):
                    if repaired.get(key) and (
                        not dossier.get(key)
                        or (
                            isinstance(repaired.get(key), list)
                            and len(repaired.get(key) or []) > len(dossier.get(key) or [])
                        )
                    ):
                        dossier[key] = repaired[key]
            else:
                last_error = err2 or last_error

    if not isinstance(dossier, dict) or not dossier:
        print(
            f"[ERROR] Dossier LLM FAILED ({label}) reason={last_error} "
            f"attempts={attempts}. Returning empty-ish dossier; no heuristic invent."
        )
        prep_slice = {"skills": resume_skills_hint, "experience": [], "projects": []}
        dossier = _empty_dossier(job_title, prep_slice, jd_excerpt, reason="llm_failed")
        compact = json.dumps(dossier, separators=(",", ":"))
        _log_dossier_field_counts(dossier, prefix="[ERROR]")
        print(f"[ERROR] Interview dossier ready: {len(compact)} chars (source=llm_failed)")
        return dossier

    dossier, compact = _shrink_dossier_to_target(dossier)
    grounding = "ok" if _dossier_grounding_ok(dossier) else "thin"
    if grounding == "thin":
        print(
            f"[WARN] Dossier LLM completed but grounding is thin ({label}) "
            f"attempts={attempts} chars={len(compact)} — questions may be weaker"
        )
    else:
        print(
            f"[INFO] Dossier LLM SUCCESS ({label}) attempts={attempts} "
            f"chars={len(compact)} grounding={grounding}"
        )
    _log_dossier_field_counts(dossier, prefix="[INFO]")
    return dossier


def _dossier_json(dossier):
    return json.dumps(dossier or {}, separators=(",", ":"))


def _shared_interview_contract_text():
    return """SHARED RULES (strict):
- Write REAL interview probes a hiring manager would ask in a live interview.
- BAN definition/textbook stems: "What is", "Explain", "Define", "List advantages", "Describe the difference between".
- Every question MUST name at least one concrete resume_anchor (from resume_anchors / experience / projects / companies)
  AND tie to a JD expectation (must_have_skills, tools, responsibilities, or transferable_bridges).
- Prefer experience/projects details (company, tech, actions) over vague soft skills.
- Prefer overlap_skills and transferable_bridges; use gap_skills only as fair probes tied to closest resume experience.
- Never treat hiring_company as the candidate's past employer unless it also appears in companies/experience.
- No coding tasks, puzzles, algorithms, or leetcode in these theory questions.
- Use ONLY the dossier. Do not invent employers, projects, or skills.

DIFFICULTY (interview depth, not textbook depth):
- beginner/easy: clarify their own past work — what they did with a tool/project/company from the dossier.
- medium: how/why they implemented, process, ownership, failure modes linking resume work to the role.
- hard: tradeoffs, architecture/judgment under JD constraints; what they would change for this role's needs.
"""


def _difficulty_depth_hint(level):
    hints = {
        "beginner": "Ask them to walk through something they actually did (tool/project/company).",
        "medium": "Ask how/why they built or decided something, linked to a JD expectation.",
        "hard": "Ask for tradeoffs/judgment applying their experience to this role's constraints.",
    }
    return hints.get(level, hints["medium"])


def _is_generic_definition_question(question_text):
    q = (question_text or "").strip().lower()
    if not q:
        return True
    banned_starts = (
        "what is ",
        "what are ",
        "what do you mean by ",
        "explain ",
        "define ",
        "list the ",
        "list advantages",
        "describe the difference",
        "tell me about yourself",
        "why should we hire",
    )
    if any(q.startswith(b) for b in banned_starts):
        return True
    # Generic role quiz without personalization markers is hard to detect; stem ban covers most.
    return False


def _coerce_text_field(value, max_chars=200) -> str:
    """Coerce LLM fields that may be str, dict, or list into a single string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return _shorten_text(value.strip(), max_chars)
    if isinstance(value, dict):
        parts = []
        for key in (
            "company", "project", "name", "title", "role", "tech", "actions",
            "skill", "expectation", "description", "jd_anchor", "resume_anchor",
        ):
            v = value.get(key)
            if isinstance(v, list):
                joined = ", ".join(str(x).strip() for x in v if str(x).strip())
                if joined:
                    parts.append(joined)
            elif v is not None and str(v).strip():
                parts.append(str(v).strip())
        if not parts:
            parts = [str(v).strip() for v in value.values() if v is not None and str(v).strip()]
        return _shorten_text(" | ".join(parts), max_chars)
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            text = _coerce_text_field(item, max_chars=80)
            if text:
                parts.append(text)
        return _shorten_text("; ".join(parts), max_chars)
    return _shorten_text(str(value).strip(), max_chars)


def _normalize_question_items(raw_questions, level, weight):
    """Normalize LLM output to {question, difficulty, weight}; drop empty."""
    out = []
    for item in raw_questions or []:
        if isinstance(item, str):
            q_text = item.strip()
            item = {"question": q_text}
        if not isinstance(item, dict):
            continue
        q_text = _coerce_text_field(item.get("question"), max_chars=800)
        if not q_text:
            continue
        out.append({
            "question": q_text,
            "difficulty": level,
            "weight": weight,
            "resume_anchor": _coerce_text_field(
                item.get("resume_anchor"), max_chars=160
            ),
            "jd_anchor": _coerce_text_field(
                item.get("jd_anchor") or item.get("jd_expectation"), max_chars=160
            ),
        })
    return out


def _strip_internal_question_fields(questions):
    cleaned = []
    for q in questions or []:
        if not isinstance(q, dict):
            continue
        cleaned.append({
            "question": q.get("question", ""),
            "difficulty": q.get("difficulty", ""),
            "weight": q.get("weight", 1),
            **({"requires_code": True} if q.get("requires_code") else {}),
        })
    return cleaned


def _build_theory_prompt(job_title, dossier, level, count, weight, mode="core",
                         resume_pct=50, jd_pct=50, blend_pct_resume=50, blend_pct_jd=50):
    dossier_blob = _dossier_json(dossier)
    mode_block = {
        "core": (
            "MODE: core (resume-primary).\n"
            "Focus mostly on resume experience/projects; use JD to aim the probe at role expectations.\n"
            "About 70% resume grounding, 30% JD alignment."
        ),
        "split_resume": (
            f"MODE: split — RESUME bucket (~{resume_pct}%).\n"
            "Ground deeply in resume experience/projects/tools.\n"
            "Still briefly connect to a JD expectation so it feels role-relevant."
        ),
        "split_jd": (
            f"MODE: split — ROLE-EXPECTATION bucket (~{jd_pct}%).\n"
            "Probe JD must-haves/responsibilities, but ALWAYS ground in closest resume overlap "
            "or a fair gap tied to the candidate's nearest experience. "
            "Do NOT ask generic textbook JD theory."
        ),
        "blend": (
            f"MODE: blend ({blend_pct_resume}% resume / {blend_pct_jd}% JD per question).\n"
            "Each question must meaningfully combine a resume_anchor with a JD expectation "
            "(prefer overlap_skills; use gap_skills only when tied to closest experience)."
        ),
        "hybrid_resume": (
            f"MODE: hybrid resume-only bucket (~{resume_pct}% of hybrid).\n"
            "Deep resume probes; still name a JD expectation for relevance."
        ),
        "hybrid_jd": (
            f"MODE: hybrid role-expectation bucket (~{jd_pct}% of hybrid).\n"
            "JD expectations grounded in closest resume overlap or acknowledged gap — not textbook quizzes."
        ),
        "hybrid_blend": (
            f"MODE: hybrid blend bucket ({blend_pct_resume}% resume / {blend_pct_jd}% JD).\n"
            "Each question must integrate both a resume_anchor and a JD expectation."
        ),
    }.get(mode, "MODE: core.")

    return f"""You are an expert technical interviewer writing live interview questions for **{job_title}**.

{_shared_interview_contract_text()}
{_difficulty_depth_hint(level)}

{mode_block}

CANDIDATE/ROLE DOSSIER (LLM-synthesized; use ONLY this; do not invent employers/projects not listed):
{dossier_blob}

Return ONLY a JSON array with EXACTLY {count} objects:
[{{"question":"...","difficulty":"{level}","weight":{weight},"resume_anchor":"short string","jd_anchor":"short string"}}]

resume_anchor and jd_anchor MUST be plain short strings (not objects/arrays).
No markdown. No extra text."""


def _generate_questions_with_retries(prompt, level, count, weight, model, max_retries=None):
    """Generate questions with a hard retry cap; accept best partial on last try."""
    if count <= 0:
        return []
    max_retries = QUESTION_GEN_MAX_RETRIES if max_retries is None else max_retries
    best = []
    for attempt in range(max_retries):
        try:
            response = try_ollama_chat(prompt.strip(), model=model)
            raw = response["message"]["content"]
            questions = _normalize_question_items(extract_json_array(raw), level, weight)
            if len(questions) >= count:
                return questions[:count]
            if len(questions) > len(best):
                best = questions
            print(
                f"[WARNING] Got {len(questions)} {level} questions instead of {count} "
                f"(attempt {attempt + 1}/{max_retries})."
            )
        except Exception as e:
            print(f"[ERROR] Failed to generate {level} questions: {e}")
    if best:
        print(f"[WARN] Accepting {len(best)}/{count} {level} questions after retries.")
    return best


def _repair_generic_questions(questions, job_title, dossier, level, weight, model):
    """One repair pass for definition-style questions."""
    if not questions:
        return questions
    good = []
    bad_idxs = []
    for i, q in enumerate(questions):
        if _is_generic_definition_question(q.get("question")):
            bad_idxs.append(i)
        else:
            good.append(q)
    if not bad_idxs or QUESTION_REPAIR_MAX_PASSES < 1:
        return questions

    need = len(bad_idxs)
    prompt = _build_theory_prompt(job_title, dossier, level, need, weight, mode="core")
    prompt += (
        "\n\nIMPORTANT: Previous output was too generic/textbook. "
        "Replace with interview probes that name resume_anchors from the dossier."
    )
    replacements = _generate_questions_with_retries(prompt, level, need, weight, model, max_retries=2)
    # Rebuild keeping order: use replacements for bad slots when available
    result = list(questions)
    ri = 0
    for idx in bad_idxs:
        if ri < len(replacements):
            result[idx] = replacements[ri]
            ri += 1
    # Drop remaining generics if repair failed
    result = [q for q in result if not _is_generic_definition_question(q.get("question"))]
    return result


def filter_questions_batch(questions, job_title, dossier, level, weight, model, target_count):
    """Filter generics, one repair pass, trim/keep up to target_count."""
    questions = _normalize_question_items(questions, level, weight)
    questions = _repair_generic_questions(questions, job_title, dossier, level, weight, model)
    return questions[:target_count] if target_count else questions


def generate_core_questions(
    structured_resume,
    job_title,
    job_description,
    beginner_count=2,
    medium_count=2,
    hard_count=2,
    model="llama3",
    dossier=None,
):
    if dossier is None:
        dossier = build_interview_dossier(structured_resume, job_title, job_description, model=model)

    def generate_questions_by_level(level, count, weight):
        if count <= 0:
            return []
        prompt = _build_theory_prompt(job_title, dossier, level, count, weight, mode="core")
        qs = _generate_questions_with_retries(prompt, level, count, weight, model)
        return filter_questions_batch(qs, job_title, dossier, level, weight, model, count)

    print("[INFO] Generating core questions by difficulty (dossier-backed)...")
    beginner_qs = generate_questions_by_level("beginner", beginner_count, 1)
    medium_qs = generate_questions_by_level("medium", medium_count, 3)
    hard_qs = generate_questions_by_level("hard", hard_count, 5)

    print(f"[DEBUG] Beginner: {len(beginner_qs)} | Medium: {len(medium_qs)} | Hard: {len(hard_qs)}")

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }

# === CODING QUESTIONS GENERATION ===

def generate_coding_questions(
    structured_resume,
    job_title,
    job_description,
    coding_count=0,
    model="llama3",
    dossier=None,
):
    """
    Generate coding/programming interview questions from compact dossier skills.
    Weights: 1=beginner, 3=medium, 5=hard.
    """
    if coding_count <= 0:
        return []

    if dossier is None:
        dossier = build_interview_dossier(structured_resume, job_title, job_description, model=model)

    # Prefer overlap, then resume languages/skills, then must-haves/tools from LLM dossier
    coding_focus = {
        "job_title": job_title,
        "overlap_skills": (dossier.get("overlap_skills") or [])[:10],
        "resume_skills": (dossier.get("resume_skills") or [])[:12],
        "must_have_skills": (dossier.get("must_have_skills") or [])[:10],
        "tools": (dossier.get("tools") or [])[:6],
        "gap_skills": (dossier.get("gap_skills") or [])[:6],
        "experience_hints": [
            {"company": e.get("company"), "title": e.get("title")}
            for e in (dossier.get("experience") or [])[:3]
        ],
        "project_hints": [
            {"name": p.get("name"), "tools": (p.get("tools") or [])[:4]}
            for p in (dossier.get("projects") or [])[:3]
        ],
    }
    focus_blob = json.dumps(coding_focus, separators=(",", ":"))

    # Spread weights across the requested count
    weights = []
    for i in range(coding_count):
        if i % 3 == 0:
            weights.append(1)
        elif i % 3 == 1:
            weights.append(3)
        else:
            weights.append(5)

    prompt = f"""You are an expert technical interviewer for **{job_title}**.

Generate CLEAR, PRECISE, IMPLEMENTABLE coding tasks (NOT theory).

SKILL FOCUS from LLM interview dossier (prioritize overlap_skills, language from resume_skills):
{focus_blob}

RULES:
1. Every item MUST be a direct coding task: "Write a function…", "Write SQL…", "Parse…", "Given X return Y…".
2. Prefer languages/tools the candidate lists in resume_skills/overlap_skills. If JD language differs, prioritize resume language but use JD-style logic from must_have_skills/tools.
3. Unambiguous tasks with a clear expected output; short example I/O when helpful.
4. Difficulty by weight:
   - weight 1 (easy): simple transform/filter/parse/basic SQL
   - weight 3 (medium): joins/aggregation, API filter, regex, multi-step transform
   - weight 5 (hard): mini utility (retry/pagination), complex SQL, branching + error handling
5. BAN: vague discussion, system design essays, unrelated LeetCode puzzles, multi-day projects.
6. Do not invent languages or libraries not present in the skill focus.

Return ONLY a JSON array with EXACTLY {coding_count} items. Use these weights in order: {weights}
[
  {{"question":"Write a ...","difficulty":"coding","weight":1}}
]
No markdown. JSON ONLY."""

    print(f"[INFO] Generating {coding_count} coding questions (dossier-backed)...")
    best = []
    for attempt in range(QUESTION_GEN_MAX_RETRIES):
        try:
            response = try_ollama_chat(prompt.strip(), model=model)
            raw = response["message"]["content"]
            questions = extract_json_array(raw)
            normalized = []
            for i, item in enumerate(questions or []):
                if isinstance(item, str):
                    item = {"question": item}
                if not isinstance(item, dict):
                    continue
                q_text = (item.get("question") or "").strip()
                if not q_text:
                    continue
                w = item.get("weight")
                if w not in (1, 3, 5):
                    w = weights[i] if i < len(weights) else 3
                normalized.append({
                    "question": q_text,
                    "difficulty": "coding",
                    "weight": w,
                })
            if len(normalized) >= coding_count:
                best = normalized[:coding_count]
                break
            if len(normalized) > len(best):
                best = normalized
            print(
                f"[WARNING] Got {len(normalized)} coding questions instead of {coding_count} "
                f"(attempt {attempt + 1}/{QUESTION_GEN_MAX_RETRIES})."
            )
        except Exception as e:
            print(f"[ERROR] Failed to generate coding questions: {e}")

    print(f"[DEBUG] Coding questions generated: {len(best)}")
    return best

# === END OF CODING QUESTIONS GENERATION ===

# === CORE QUESTION GENERATION WITH SPLIT INTEGRATED ===

def generate_split_questions(
    structured_resume,
    job_title,
    job_description,
    beginner_count=2,
    medium_count=2,
    hard_count=2,
    resume_pct=50,
    jd_pct=50,
    model="llama3",
    dossier=None,
):
    if dossier is None:
        dossier = build_interview_dossier(structured_resume, job_title, job_description, model=model)

    def generate_questions_by_source(level, count, weight, source):
        if count <= 0:
            return []
        mode = "split_resume" if source == "resume" else "split_jd"
        prompt = _build_theory_prompt(
            job_title,
            dossier,
            level,
            count,
            weight,
            mode=mode,
            resume_pct=resume_pct,
            jd_pct=jd_pct,
        )
        qs = _generate_questions_with_retries(prompt, level, count, weight, model)
        return filter_questions_batch(qs, job_title, dossier, level, weight, model, count)

    total = beginner_count + medium_count + hard_count
    if total == 0:
        return {"beginner": [], "medium": [], "hard": []}

    resume_total = round(total * resume_pct / 100)
    jd_total = total - resume_total

    print(f"\n{Fore.BLUE}=== SPLIT MODE DEBUG ==={Style.RESET_ALL}")
    print(f"{Fore.CYAN}[REQUESTED]{Style.RESET_ALL} Resume={resume_pct}% ({resume_total}), JD={jd_pct}% ({jd_total})")

    def distribute(bucket_total, total):
        if bucket_total == 0:
            return (0, 0, 0)
        b = round(bucket_total * (beginner_count / total))
        m = round(bucket_total * (medium_count / total))
        h = round(bucket_total * (hard_count / total))
        while b + m + h < bucket_total:
            b += 1
        while b + m + h > bucket_total:
            if b > 0:
                b -= 1
            elif m > 0:
                m -= 1
            else:
                h -= 1
        return (b, m, h)

    resume_dist = list(distribute(resume_total, total))
    jd_dist = list(distribute(jd_total, total))

    print(f"{Fore.CYAN}[BALANCED]{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}Resume -> Beginner={resume_dist[0]}, Medium={resume_dist[1]}, Hard={resume_dist[2]}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}JD     -> Beginner={jd_dist[0]}, Medium={jd_dist[1]}, Hard={jd_dist[2]}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}=========================={Style.RESET_ALL}\n")

    beginner_qs, medium_qs, hard_qs = [], [], []

    beginner_qs.extend(generate_questions_by_source("beginner", resume_dist[0], 1, "resume"))
    beginner_qs.extend(generate_questions_by_source("beginner", jd_dist[0], 1, "jd"))

    medium_qs.extend(generate_questions_by_source("medium", resume_dist[1], 3, "resume"))
    medium_qs.extend(generate_questions_by_source("medium", jd_dist[1], 3, "jd"))

    hard_qs.extend(generate_questions_by_source("hard", resume_dist[2], 5, "resume"))
    hard_qs.extend(generate_questions_by_source("hard", jd_dist[2], 5, "jd"))

    print(f"[DONE] Final counts -> Beginner: {len(beginner_qs)}, Medium: {len(medium_qs)}, Hard: {len(hard_qs)}")

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }

# === END OF CORE QUESTION GENERATION WITH SPLIT INTEGRATED ===


# === CORE QUESTION GENERATION WITH BLEND INTEGRATED ===

def generate_blend_questions(
    structured_resume,
    job_title,
    job_description,
    beginner_count=2,
    medium_count=2,
    hard_count=2,
    blend_pct_resume=50,
    blend_pct_jd=50,
    model="llama3",
    dossier=None,
):
    """Generate interview questions blending resume and JD via compact dossier."""
    if dossier is None:
        dossier = build_interview_dossier(structured_resume, job_title, job_description, model=model)

    def generate_questions_blend(level, count, weight):
        if count <= 0:
            return []
        prompt = _build_theory_prompt(
            job_title,
            dossier,
            level,
            count,
            weight,
            mode="blend",
            blend_pct_resume=blend_pct_resume,
            blend_pct_jd=blend_pct_jd,
        )
        qs = _generate_questions_with_retries(prompt, level, count, weight, model)
        return filter_questions_batch(qs, job_title, dossier, level, weight, model, count)

    print(f"[INFO] Generating blended questions (Resume {blend_pct_resume}% | JD {blend_pct_jd}%)")

    beginner_qs, medium_qs, hard_qs = [], [], []
    if beginner_count > 0:
        beginner_qs = generate_questions_blend("beginner", beginner_count, 1)
    if medium_count > 0:
        medium_qs = generate_questions_blend("medium", medium_count, 3)
    if hard_count > 0:
        hard_qs = generate_questions_blend("hard", hard_count, 5)

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }

# === END OF CORE QUESTION GENERATION WITH BLEND INTEGRATED ===


# === CORE QUESTION GENERATION WITH HYBRID INTEGRATED ===

def generate_hybrid_questions(
    structured_resume,
    job_title,
    job_description,
    beginner_count=2,
    medium_count=2,
    hard_count=2,
    resume_pct=40,
    jd_pct=30,
    blend_pct_resume=50,
    blend_pct_jd=50,
    model="llama3",
    dossier=None,
):
    """
    Hybrid mode: 40% blended questions, 60% split (resume vs JD).
    Preserves user-requested beginner/medium/hard counts.
    """
    if dossier is None:
        dossier = build_interview_dossier(structured_resume, job_title, job_description, model=model)

    total = beginner_count + medium_count + hard_count
    if total == 0:
        return {"beginner": [], "medium": [], "hard": []}

    blend_total = round(total * 0.4)
    split_total = total - blend_total
    resume_total = round(split_total * (resume_pct / 100))
    jd_total = split_total - resume_total

    print(f"[INFO] Hybrid distribution -> Resume-only: {resume_total}, JD-only: {jd_total}, Blend: {blend_total}")

    def distribute(bucket_total, total):
        if bucket_total == 0 or total == 0:
            return (0, 0, 0)
        b = round(bucket_total * (beginner_count / total))
        m = round(bucket_total * (medium_count / total))
        h = round(bucket_total * (hard_count / total))
        if b + m + h == 0 and bucket_total > 0:
            b = bucket_total
        while b + m + h < bucket_total:
            b += 1
        while b + m + h > bucket_total:
            if b > 0:
                b -= 1
            elif m > 0:
                m -= 1
            else:
                h -= 1
        return (b, m, h)

    resume_dist = list(distribute(resume_total, total))
    jd_dist = list(distribute(jd_total, total))
    blend_dist = list(distribute(blend_total, total))

    def rebalance_buckets(resume_dist, jd_dist, blend_dist, beginner_count, medium_count, hard_count):
        totals = [
            resume_dist[0] + jd_dist[0] + blend_dist[0],
            resume_dist[1] + jd_dist[1] + blend_dist[1],
            resume_dist[2] + jd_dist[2] + blend_dist[2],
        ]
        requested = [beginner_count, medium_count, hard_count]
        for _ in range(30):
            for i in range(3):
                if totals[i] > requested[i]:
                    for j in range(3):
                        if totals[j] < requested[j]:
                            totals[i] -= 1
                            totals[j] += 1
                            if jd_dist[i] > 0:
                                jd_dist[i] -= 1
                                jd_dist[j] += 1
                            elif resume_dist[i] > 0:
                                resume_dist[i] -= 1
                                resume_dist[j] += 1
                            elif blend_dist[i] > 0:
                                blend_dist[i] -= 1
                                blend_dist[j] += 1
                            break
            if totals == requested:
                break
        return resume_dist, jd_dist, blend_dist

    resume_dist, jd_dist, blend_dist = rebalance_buckets(
        resume_dist, jd_dist, blend_dist, beginner_count, medium_count, hard_count
    )

    print(f"\n{Fore.CYAN}[BALANCED]{Style.RESET_ALL}")
    print(f"  Resume -> {Fore.YELLOW}BEGINNER={resume_dist[0]}, MEDIUM={resume_dist[1]}, HARD={resume_dist[2]}{Style.RESET_ALL}")
    print(f"  JD     -> {Fore.GREEN}BEGINNER={jd_dist[0]}, MEDIUM={jd_dist[1]}, HARD={jd_dist[2]}{Style.RESET_ALL}")
    print(f"  Blend  -> {Fore.MAGENTA}BEGINNER={blend_dist[0]}, MEDIUM={blend_dist[1]}, HARD={blend_dist[2]}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}==========================\n{Style.RESET_ALL}")

    beginner_qs, medium_qs, hard_qs = [], [], []

    def generate_from_source(level, count, weight, source):
        if count <= 0:
            return []
        mode = "hybrid_resume" if source == "resume" else "hybrid_jd"
        prompt = _build_theory_prompt(
            job_title,
            dossier,
            level,
            count,
            weight,
            mode=mode,
            resume_pct=resume_pct,
            jd_pct=jd_pct,
        )
        qs = _generate_questions_with_retries(prompt, level, count, weight, model)
        return filter_questions_batch(qs, job_title, dossier, level, weight, model, count)

    def generate_blended(level, count, weight):
        if count <= 0:
            return []
        prompt = _build_theory_prompt(
            job_title,
            dossier,
            level,
            count,
            weight,
            mode="hybrid_blend",
            blend_pct_resume=blend_pct_resume,
            blend_pct_jd=blend_pct_jd,
        )
        qs = _generate_questions_with_retries(prompt, level, count, weight, model)
        return filter_questions_batch(qs, job_title, dossier, level, weight, model, count)

    beginner_qs.extend(generate_from_source("beginner", resume_dist[0], 1, "resume"))
    medium_qs.extend(generate_from_source("medium", resume_dist[1], 3, "resume"))
    hard_qs.extend(generate_from_source("hard", resume_dist[2], 5, "resume"))

    beginner_qs.extend(generate_from_source("beginner", jd_dist[0], 1, "jd"))
    medium_qs.extend(generate_from_source("medium", jd_dist[1], 3, "jd"))
    hard_qs.extend(generate_from_source("hard", jd_dist[2], 5, "jd"))

    beginner_qs.extend(generate_blended("beginner", blend_dist[0], 1))
    medium_qs.extend(generate_blended("medium", blend_dist[1], 3))
    hard_qs.extend(generate_blended("hard", blend_dist[2], 5))

    def trim_or_pad(lst, target, level, weight):
        if len(lst) > target:
            return lst[:target]
        # Cap pad attempts to avoid token burn (replaces unbounded loop + Fallback stubs)
        pad_attempts = 0
        max_pad_attempts = max(target - len(lst), 0) * 2 + 1
        while len(lst) < target and pad_attempts < max_pad_attempts:
            pad_attempts += 1
            need = target - len(lst)
            new_qs = generate_from_source(level, need, weight, "resume")
            if not new_qs:
                new_qs = generate_blended(level, need, weight)
            if not new_qs:
                new_qs = generate_from_source(level, need, weight, "jd")
            if not new_qs:
                break
            lst.extend(new_qs)
            if len(lst) > target:
                lst = lst[:target]
        return lst

    beginner_qs = trim_or_pad(beginner_qs, beginner_count, "beginner", 1)
    medium_qs = trim_or_pad(medium_qs, medium_count, "medium", 3)
    hard_qs = trim_or_pad(hard_qs, hard_count, "hard", 5)

    print(f"[DONE] Final counts -> Beginner: {len(beginner_qs)}, Medium: {len(medium_qs)}, Hard: {len(hard_qs)}")

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }


def run_pipeline_from_api(
    resume_path,
    job_title,
    job_description,
    question_counts={'beginner': 1, 'medium': 1, 'hard': 1},
    include_answers=False,
    split=False,
    resume_pct=50,
    jd_pct=50,
    blend=False,
    blend_pct_resume=50,   # for blend mode: percentage weight of resume context
    blend_pct_jd=50,       # for blend mode: percentage weight of JD context
    max_retries=3,
    skills_list=None,
    resume_id=None,
    jd_id=None,
):

    """
    Run the resume pipeline with data from frontend instead of config file.
    Either resume_path (file) or skills_list must be provided.

    Dossier-first: extract text → load/build dossier (local cache by resume_id+jd_id)
    → generate questions. Does not call structured-resume LLM.
    Sample answers are deferred to a later stage (even if include_answers=True).
    """
    
    resolved_model = resolve_ollama_model_name()

    for attempt in range(max_retries):
        try:
            print(f"\n[INFO] API Attempt {attempt + 1} of {max_retries}")

            if split and blend:
                mode_label = "hybrid"
            elif split:
                mode_label = "split"
            elif blend:
                mode_label = "blend"
            else:
                mode_label = "core"

            with track_token_usage(label="question_generation") as token_tracker:
                if not job_title or not job_description:
                    raise ValueError("Job title and description are required")

                resume_text = ""
                dossier_cache_status = "skip"

                if skills_list:
                    structured_from_skills = build_structured_data_from_skills(skills_list)
                    if not structured_from_skills or not structured_from_skills.get("skills"):
                        return {
                            "success": False,
                            "error": "Please provide at least one skill (comma-separated).",
                        }
                    candidate_name = "candidate"
                    skills_list = structured_from_skills.get("skills") or skills_list
                    print(
                        f"[INFO] Processing skills-based profile for: {job_title} "
                        f"({len(skills_list)} skills)"
                    )
                else:
                    if not resume_path or not os.path.exists(resume_path):
                        raise FileNotFoundError(f"Resume not found: {resume_path}")

                    print(f"[INFO] Processing resume for: {job_title}")
                    print(f"[INFO] Question counts: {question_counts}")
                    print(f"[INFO] Include answers: {include_answers}")
                    print(f"[INFO] Ollama model: {resolved_model}")
                    print(f"[INFO] Mode: {mode_label} | Split={split} ({resume_pct}%/{jd_pct}%) | Blend={blend}")

                    resume_text = extract_text_from_resume(resume_path)
                    from common.document_validation import validate_resume_text
                    is_valid_resume, resume_validation_error = validate_resume_text(resume_text)
                    if not is_valid_resume:
                        raise ResumeParseError(resume_validation_error)
                    candidate_name = _candidate_name_from_text(resume_text)

                # Compact JD+resume dossier: local cache by resume_id+jd_id when available
                can_cache = bool((resume_id or "").strip() and (jd_id or "").strip())
                dossier = None
                if can_cache:
                    dossier = load_dossier(resume_id, jd_id)
                    if dossier:
                        dossier_cache_status = "hit"
                        print(
                            f"[INFO] Dossier cache hit resume_id={resume_id} jd_id={jd_id}"
                        )
                    else:
                        dossier_cache_status = "miss"
                        print(
                            f"[INFO] Dossier cache miss resume_id={resume_id} jd_id={jd_id}"
                        )
                else:
                    print("[INFO] Dossier cache skipped (missing resume_id or jd_id)")

                if not dossier:
                    dossier = build_interview_dossier_from_text(
                        resume_text,
                        job_title,
                        job_description,
                        model=resolved_model,
                        skills_list=skills_list,
                    )
                    if can_cache:
                        if (dossier or {}).get("source") == "llm_failed":
                            print(
                                "[WARN] Skipping dossier cache save (source=llm_failed); "
                                "will retry LLM on next generate"
                            )
                        else:
                            save_dossier(resume_id, jd_id, dossier, job_title=job_title)

                structured_data = _stub_structured_from_dossier(
                    dossier, candidate_name, skills_list=skills_list
                )

                # Create temporary output directory
                import tempfile
                temp_dir = tempfile.mkdtemp(prefix=f"resume_processing_{candidate_name}_")

                # File paths
                parsed_resume_path = os.path.join(temp_dir, "parsed_resume.json")
                questions_path = os.path.join(temp_dir, "questions.csv")

                # Save stub + dossier for debugging
                save_json_output(
                    {"stub": structured_data, "dossier": dossier},
                    parsed_resume_path,
                )

                # === Generate questions ===
                if split and blend:
                    core_questions = generate_hybrid_questions(
                        structured_data,
                        job_title,
                        job_description,
                        question_counts.get('beginner', 1),
                        question_counts.get('medium', 1),
                        question_counts.get('hard', 1),
                        resume_pct,
                        jd_pct,
                        blend_pct_resume=blend_pct_resume,
                        blend_pct_jd=blend_pct_jd,
                        model=resolved_model,
                        dossier=dossier,
                    )
                elif split:
                    core_questions = generate_split_questions(
                        structured_data,
                        job_title,
                        job_description,
                        question_counts.get('beginner', 1),
                        question_counts.get('medium', 1),
                        question_counts.get('hard', 1),
                        resume_pct,
                        jd_pct,
                        model=resolved_model,
                        dossier=dossier,
                    )
                elif blend:
                    core_questions = generate_blend_questions(
                        structured_data,
                        job_title,
                        job_description,
                        question_counts.get('beginner', 1),
                        question_counts.get('medium', 1),
                        question_counts.get('hard', 1),
                        blend_pct_resume,
                        blend_pct_jd,
                        model=resolved_model,
                        dossier=dossier,
                    )
                else:
                    core_questions = generate_core_questions(
                        structured_data,
                        job_title,
                        job_description,
                        question_counts.get('beginner', 1),
                        question_counts.get('medium', 1),
                        question_counts.get('hard', 1),
                        model=resolved_model,
                        dossier=dossier,
                    )

                # Generate coding questions if requested
                coding_count = question_counts.get('coding', 0)
                if coding_count > 0:
                    print(f"[INFO] Generating {coding_count} coding questions...")
                    coding_questions = generate_coding_questions(
                        structured_data,
                        job_title,
                        job_description,
                        coding_count,
                        model=resolved_model,
                        dossier=dossier,
                    )

                    # Categorize coding questions by weight and merge into existing categories
                    # weight 1 → beginner, weight 3 → medium, weight 5 → hard
                    for q in coding_questions:
                        weight = q.get('weight', 5)  # Default to 5 if weight missing
                        # Mark as coding question
                        q['requires_code'] = True
                        # Update difficulty to match category
                        if weight == 1:
                            q['difficulty'] = 'beginner'
                            core_questions['beginner'].append(q)
                        elif weight == 3:
                            q['difficulty'] = 'medium'
                            core_questions['medium'].append(q)
                        else:  # weight == 5 or any other value
                            q['difficulty'] = 'hard'
                            core_questions['hard'].append(q)

                    print(f"[DEBUG] Coding questions categorized: "
                          f"Beginner={sum(1 for q in coding_questions if q.get('weight') == 1)}, "
                          f"Medium={sum(1 for q in coding_questions if q.get('weight') == 3)}, "
                          f"Hard={sum(1 for q in coding_questions if q.get('weight') == 5)}")
                else:
                    # Ensure coding key doesn't exist if not generating
                    if 'coding' in core_questions:
                        del core_questions['coding']

                # Save questions to CSV
                save_questions_to_csv(core_questions, questions_path)

                answer_generation = {
                    "requested": include_answers,
                    "model": resolved_model,
                    "generated_count": 0,
                    "fallback_count": 0,
                    "fallback_examples": [],
                    "deferred": bool(include_answers),
                }

                # Sample answers deferred: dossier-based answers land in a later stage
                if include_answers:
                    print(
                        "[INFO] Sample answers deferred; use dossier-based answers in a later stage"
                    )
                else:
                    print("[INFO] Skipping answer generation as requested.")

                final_csv_path = questions_path

                # Read back questions
                questions = read_questions_from_csv(final_csv_path)

                token_tracker.log(
                    extra=(
                        f"mode={mode_label} questions={len(questions)} "
                        f"include_answers={include_answers} "
                        f"dossier_cache={dossier_cache_status}"
                    )
                )
                token_usage = token_tracker.as_dict()
                token_usage["mode"] = mode_label
                token_usage["dossier_cache"] = dossier_cache_status

                return {
                    "success": True,
                    "candidate": candidate_name,
                    "questions": questions,
                    "questions_count": len(questions),
                    "generator": "ollama_pipeline",
                    "ollama_model": resolved_model,
                    "answer_generation": answer_generation,
                    "parsed_resume": structured_data,
                    "dossier": dossier,
                    "temp_dir": temp_dir,
                    "qa_csv": final_csv_path,
                    "token_usage": token_usage,
                }

        except Exception as e:
            print(f"[ERROR] Attempt {attempt + 1} failed: {e}")
            import traceback; traceback.print_exc()

            if attempt == max_retries - 1:
                return {
                    "success": False,
                    "error": f"Max retries reached: {e}"
                }
            print("[INFO] Retrying...\n")

