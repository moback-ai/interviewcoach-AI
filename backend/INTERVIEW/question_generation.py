"""Interview dossier + question generation (core/split/blend/hybrid/coding) + API pipeline."""
from __future__ import annotations

import ast
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
from INTERVIEW.dossier_store import DOSSIER_SCHEMA_VERSION, load_dossier, save_dossier


QUESTION_GEN_MAX_RETRIES = 3
DOSSIER_LLM_MAX_RETRIES = 8
DOSSIER_LLM_MAX_TOKENS = 3072
DOSSIER_LLM_TEMPERATURE = 0.2
DOSSIER_TARGET_MAX_CHARS = 9000
JD_PREP_EXCERPT_MAX = 5000
HIGHLIGHTS_MAX = 4
JD_HIGHLIGHTS_MAX = 8
HIGHLIGHT_ITEM_MAX = 140
RESUME_TEXT_DOSSIER_MAX = 10000
QUESTION_REPAIR_MAX_PASSES = 1
QUESTION_BATCH_MAX_TOKENS = 3072
QUESTION_BATCH_TEMPERATURE = 0.3
QUESTION_BATCH_MAX_REFILL_ROUNDS = 8


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


def _coerce_highlights(*sources, limit=HIGHLIGHTS_MAX, item_max=HIGHLIGHT_ITEM_MAX):
    """
    Normalize bullet highlights from lists/strings.
    Never stringifies a list (avoids \"['Interacted...\" garbage).
    Accepts legacy description / summary / jd_excerpt as sources.
    """
    raw_items = []

    def _extend_from_string(text: str):
        text = (text or "").strip()
        if not text:
            return
        if text.startswith("[") and text.endswith("]"):
            parsed = None
            try:
                parsed = json.loads(text)
            except Exception:
                try:
                    parsed = ast.literal_eval(text)
                except Exception:
                    parsed = None
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str) and item.strip():
                        raw_items.append(item.strip())
                    elif item is not None:
                        s = str(item).strip()
                        if s:
                            raw_items.append(s)
                return
        parts = [p.strip(" -•\t") for p in re.split(r"[\n;]+", text) if p.strip(" -•\t")]
        if len(parts) > 1:
            raw_items.extend(parts)
        else:
            raw_items.append(text)

    for source in sources:
        if source is None or source == "":
            continue
        if isinstance(source, list):
            for item in source:
                if isinstance(item, str) and item.strip():
                    raw_items.append(item.strip())
                elif isinstance(item, dict):
                    for key in ("text", "highlight", "description", "summary", "action"):
                        val = item.get(key)
                        if isinstance(val, str) and val.strip():
                            raw_items.append(val.strip())
                            break
                elif item is not None:
                    s = str(item).strip()
                    if s and not (s.startswith("[") and "'," in s):
                        raw_items.append(s)
        elif isinstance(source, str):
            _extend_from_string(source)

    seen = set()
    out = []
    for item in raw_items:
        shortened = _shorten_text(item, item_max)
        key = _normalize_skill_token(shortened)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(shortened)
        if len(out) >= limit:
            break
    return out


def _entry_highlights_artifact(entry: dict) -> str:
    """First 1–2 highlights (or legacy description) for anchor examples."""
    if not isinstance(entry, dict):
        return ""
    highlights = entry.get("highlights")
    if isinstance(highlights, list):
        parts = [h.strip() for h in highlights[:2] if isinstance(h, str) and h.strip()]
        if parts:
            return "; ".join(parts)
    legacy = entry.get("description") or entry.get("summary") or ""
    if isinstance(legacy, list):
        parts = [str(h).strip() for h in legacy[:2] if str(h).strip()]
        return "; ".join(parts)
    if isinstance(legacy, str):
        return legacy.strip()
    return ""


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
        highlights = _coerce_highlights(
            exp.get("highlights"),
            exp.get("description"),
            exp.get("summary"),
            limit=HIGHLIGHTS_MAX,
        )
        item = {
            "title": _shorten_text(exp.get("title") or "", 60),
            "company": _shorten_text(exp.get("company") or "", 40),
            "highlights": highlights,
        }
        if item["title"] or item["company"] or item["highlights"]:
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
        highlights = _coerce_highlights(
            proj.get("highlights"),
            proj.get("description"),
            proj.get("summary"),
            limit=HIGHLIGHTS_MAX,
        )
        item = {
            "name": _shorten_text(proj.get("name") or "", 50),
            "role": _shorten_text(proj.get("role") or "", 40),
            "tools": [str(t) for t in tools[:6] if t],
            "highlights": highlights,
        }
        if item["name"] or item["highlights"]:
            projects.append(item)

    return {
        "name": _shorten_text(structured_resume.get("name") or "", 60),
        "summary": _shorten_text(structured_resume.get("summary") or "", 220),
        "skills": _collect_resume_skills(structured_resume)[:20],
        "experience": experiences[:5],
        "projects": projects[:5],
    }


def _empty_dossier(job_title, prep_slice=None, reason="llm_failed"):
    """Hard-failure shell only — no invented JD metrics or fake quality fields."""
    prep_slice = prep_slice or {}
    experience = _coerce_experience_list(prep_slice.get("experience"), limit=5)
    projects = _coerce_project_list(prep_slice.get("projects"), limit=5)
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
        "experience": experience,
        "projects": projects,
        "resume_highlights": [],
        "overlap_skills": [],
        "gap_skills": [],
        "transferable_bridges": [],
        "resume_anchors": [],
        "jd_highlights": [],
        "schema_version": DOSSIER_SCHEMA_VERSION,
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
                for k in (
                    "company",
                    "title",
                    "name",
                    "role",
                    "project",
                    "description",
                    "highlight",
                    "bridge",
                )
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
                "highlights": _coerce_highlights(item, limit=HIGHLIGHTS_MAX),
            })
        elif isinstance(item, dict):
            tech = item.get("tech") or item.get("tools") or []
            if isinstance(tech, str):
                tech = [t.strip() for t in tech.split(",") if t.strip()]
            elif not isinstance(tech, list):
                tech = []
            highlights = _coerce_highlights(
                item.get("highlights"),
                item.get("description"),
                item.get("summary"),
                limit=HIGHLIGHTS_MAX,
            )
            exp = {
                "company": _shorten_text(str(item.get("company") or ""), 50),
                "title": _shorten_text(str(item.get("title") or item.get("role") or ""), 60),
                "dates": _shorten_text(str(item.get("dates") or item.get("duration") or ""), 40),
                "tech": _coerce_str_list(tech, limit=8, item_max=40),
                "highlights": highlights,
            }
            if exp["company"] or exp["title"] or exp["highlights"]:
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
                "highlights": [],
            })
        elif isinstance(item, dict):
            tech = item.get("tech") or item.get("tools") or []
            if isinstance(tech, str):
                tech = [t.strip() for t in tech.split(",") if t.strip()]
            elif not isinstance(tech, list):
                tech = []
            highlights = _coerce_highlights(
                item.get("highlights"),
                item.get("description"),
                item.get("summary"),
                limit=HIGHLIGHTS_MAX,
            )
            proj = {
                "name": _shorten_text(str(item.get("name") or item.get("project") or ""), 60),
                "role": _shorten_text(str(item.get("role") or ""), 40),
                "tech": _coerce_str_list(tech, limit=8, item_max=40),
                "highlights": highlights,
            }
            if proj["name"] or proj["highlights"]:
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
        f"jd_highlights={len(d.get('jd_highlights') or [])} "
        f"hiring_company={d.get('hiring_company') or '-'} "
        f"source={d.get('source') or '-'}"
    )


def _shrink_dossier_to_target(dossier):
    compact = json.dumps(dossier, separators=(",", ":"))
    if len(compact) <= DOSSIER_TARGET_MAX_CHARS:
        return dossier, compact
    for e in dossier.get("experience") or []:
        if isinstance(e, dict):
            e["highlights"] = _coerce_highlights(
                e.get("highlights"), e.get("description"), limit=2, item_max=100
            )
            e.pop("description", None)
            e["tech"] = (e.get("tech") or [])[:4]
    for p in dossier.get("projects") or []:
        if isinstance(p, dict):
            p["highlights"] = _coerce_highlights(
                p.get("highlights"), p.get("description"), limit=2, item_max=100
            )
            p.pop("description", None)
            p["tech"] = (p.get("tech") or [])[:4]
    for a in dossier.get("resume_anchors") or []:
        if isinstance(a, dict):
            a["actions"] = (a.get("actions") or [])[:2]
            a["tech"] = (a.get("tech") or [])[:4]
    dossier["jd_highlights"] = _coerce_highlights(
        dossier.get("jd_highlights"),
        dossier.get("jd_excerpt"),
        limit=5,
        item_max=100,
    )
    dossier.pop("jd_excerpt", None)
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
  "jd_highlights": ["4-8 JD must-haves / core duties / key tools only"],
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
      "highlights": ["2-4 interview-useful bullets: action + what + tech/system when present"]
    }}
  ],
  "projects": [
    {{
      "name": "...",
      "role": "optional",
      "tech": ["..."],
      "highlights": ["2-4 interview-useful bullets of what they built / owned"]
    }}
  ],
  "resume_skills": ["skills explicitly present in the resume"],
  "resume_highlights": ["1-5 standout resume facts useful for probing questions"],
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
      "actions": ["specific artifact or ownership worth asking about"]
    }}
  ]
}}

Rules:
- Use ONLY the provided resume/candidate text and JD text. Do not invent employers, projects, or skills.
- ALWAYS fill companies, experience, and projects when the resume mentions them (even briefly).
- Prefer precise skill/tool names over vague soft skills (do not let Agile dominate overlap_skills).
- Keep lists short: max 5 companies, 5 experience, 5 projects, 8 must_have_skills, 5 nice_to_have,
  6 responsibilities, 8 jd_highlights, 6 tools, 5 resume_highlights, 10 overlap_skills, 8 gap_skills,
  6 transferable_bridges, 10 resume_anchors, 20 resume_skills.
- SELECT highlights — do not dump every resume line. Prefer fewer strong bullets over padded ones.
  Aim for 2-4 per experience/project; use 1-2 if that is all that is concrete; omit fluff rather than fill.
- Each experience/project highlight MUST be interview-useful: concrete action + object/system + tech when present
  (e.g. "Built TPM/Retail Execution on Salesforce Lightning with Apex batch jobs").
- REJECT generic process fluff in highlights, resume_highlights, and resume_anchors.actions, including:
  delivered on time, followed Agile, worked with BA/PO, documentation only, trained users,
  "developed the provided requirements", "took care of deployments" with no system/tool detail.
- For jd_highlights: select only differentiating must-haves, core duties, and key tools/seniority context.
  Do NOT restate the entire JD or soft-collaboration filler. Prefer 4-8 strong points.
- For resume_anchors: only specific companies/projects/artifacts the interviewer can cite; actions must be concrete.
- For transferable_bridges: only real resume capability -> JD expectation links (tech/system), not soft skills.
- Output a single raw JSON object only. No markdown fences. No ```json. No commentary.
- Keep total JSON under ~{DOSSIER_TARGET_MAX_CHARS} characters.
"""


def _normalize_parsed_dossier(parsed, job_title, resume_skills_fallback=None, source="llm"):
    """Normalize LLM JSON into the canonical dossier shape."""
    resume_skills_fallback = resume_skills_fallback or []
    llm_resume_skills = _coerce_str_list(parsed.get("resume_skills"), limit=20, item_max=40)
    companies = _coerce_str_list(parsed.get("companies"), limit=5, item_max=50)
    experience = _coerce_experience_list(parsed.get("experience"), limit=5)
    projects = _coerce_project_list(parsed.get("projects"), limit=5)
    responsibilities = _coerce_str_list(parsed.get("responsibilities"), limit=6, item_max=140)
    jd_highlights = _coerce_highlights(
        parsed.get("jd_highlights"),
        parsed.get("jd_excerpt"),
        limit=JD_HIGHLIGHTS_MAX,
    )
    if not jd_highlights and responsibilities:
        jd_highlights = list(responsibilities)[:JD_HIGHLIGHTS_MAX]

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
        "responsibilities": responsibilities,
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
        "jd_highlights": jd_highlights,
        "schema_version": DOSSIER_SCHEMA_VERSION,
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
    jd_prep_text = _shorten_text(job_description, JD_PREP_EXCERPT_MAX)
    prep_blob = json.dumps(prep_slice, separators=(",", ":"))

    prompt = f"""You are building a rich interview dossier for question generation.

Job title: {job_title}

RESUME PREP SLICE (already parsed; do NOT invent employers, projects, or skills not listed):
{prep_blob}

JOB DESCRIPTION (truncated for input only; extract only the most important jd_highlights):
\"\"\"{jd_prep_text}\"\"\"

Select interview-useful highlights and anchors only — polish and keep what matters; do not dump every line.

{_dossier_json_contract_block()}
"""

    repair_suffix = (
        "\n\nIMPORTANT: Previous output was too thin (missing companies/experience/projects/"
        "resume_anchors). Re-read the resume slice and FILL those fields from what is present. "
        "Keep highlights concrete and selective (no process fluff). JSON only."
    )

    parsed, last_error, attempts = _call_dossier_llm(prompt, model, label="structured")
    dossier = None
    if isinstance(parsed, dict) and parsed:
        dossier = _normalize_parsed_dossier(
            parsed,
            job_title,
            resume_skills_fallback=prep_slice.get("skills") or [],
            source="llm",
        )
        # Prefer prep-slice experience/projects if LLM left them empty but slice has them
        if not dossier.get("experience") and prep_slice.get("experience"):
            dossier["experience"] = _coerce_experience_list(
                prep_slice.get("experience"), limit=5
            )
        if not dossier.get("projects") and prep_slice.get("projects"):
            dossier["projects"] = _coerce_project_list(
                prep_slice.get("projects"), limit=5
            )
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
        dossier = _empty_dossier(job_title, prep_slice, reason="llm_failed")
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
    jd_prep_text = _shorten_text(job_description, JD_PREP_EXCERPT_MAX)

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

JOB DESCRIPTION (truncated for input only; extract only the most important jd_highlights):
\"\"\"{jd_prep_text}\"\"\"

Extract companies, job titles, projects, tools, and concrete actions from the resume text
into experience / projects / companies / resume_anchors. This grounding is critical.
For highlights and anchors: select only interview-useful facts (action + system/tech); skip generic fluff.

{_dossier_json_contract_block()}
"""

    repair_suffix = (
        "\n\nIMPORTANT: Previous output was too thin (missing companies/experience/projects/"
        "resume_anchors). Scan the resume text again for employer names, project names, "
        "technologies, and what the candidate did. FILL those fields. Do not invent. "
        "Keep highlights concrete and selective (no process fluff). JSON only."
    )

    print(f"[INFO] Building dossier via LLM ({label})...")
    parsed, last_error, attempts = _call_dossier_llm(prompt, model, label=label)
    dossier = None
    if isinstance(parsed, dict) and parsed:
        dossier = _normalize_parsed_dossier(
            parsed,
            job_title,
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
                    "jd_highlights",
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
        dossier = _empty_dossier(job_title, prep_slice, reason="llm_failed")
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
- Write REAL interview probes a hiring manager would ask in a live interview for THIS job title.
- Adapt tone to the role domain in the dossier (technical, business, creative, operations, etc.).
- BAN definition/textbook stems: "What is", "Explain", "Define", "List advantages", "Describe the difference between".
- BAN soft/vague stems: "Tell us about your experience with", "What was your approach to",
  "What strategies would you employ", "How did you handle X" when X is only a bare skill name,
  "Describe your role in" with no concrete artifact.
- Every question MUST name at least one concrete resume artifact from the dossier:
  company, project/initiative, outcome/metric, method, or tool named in the dossier —
  AND tie to a JD expectation (must_have_skills, tools, responsibilities, or transferable_bridges).
- ONE anchor bundle per question: do not combine project from one story with outcome from another.
- Prefer experience/projects details (company, actions, outcomes) over vague soft skills.
- Prefer overlap_skills and transferable_bridges.
- gap_skills: NEVER claim the candidate already used them. Phrase as transfer:
  "Given your <resume work>, how would you approach <gap skill / JD need> for this role?"
- Never treat hiring_company as the candidate's past employer unless it also appears in companies/experience.
- No coding tasks, puzzles, algorithms, or leetcode unless the role clearly requires coding questions
  (those are handled separately). For these theory questions, stay non-leetcode.
- Use ONLY the dossier. Do not invent employers, projects, skills, or past usage of gap tools.

DIFFICULTY LADDER (must get deeper; do not rephrase the same anecdote):
- beginner/easy: walk through ONE concrete thing they did — name project/outcome/tool from dossier.
- medium: how/why/process, ownership, failure modes, or measurement — still on THEIR past work, aimed at JD.
- hard: tradeoffs and judgment applying THEIR past work to THIS role's constraints; what they would change and why.
"""


def _difficulty_depth_hint(level):
    hints = {
        "beginner": (
            "Ask them to walk through one concrete past artifact "
            "(named project/outcome/tool from the dossier)."
        ),
        "medium": (
            "Ask how/why they built or decided something, including failure modes or measurement, "
            "linked to a JD expectation."
        ),
        "hard": (
            "Ask for tradeoffs/judgment applying their concrete past work to this role's "
            "constraints (prefer transferable_bridges); not a generic strategy essay."
        ),
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
        "tell us about your experience",
        "tell me about your experience",
        "what was your approach to",
        "what strategies would you employ",
        "what considerations would you take",
        "how would you approach designing a scalable",
        "how would you balance the trade-offs between using",
    )
    if any(q.startswith(b) for b in banned_starts):
        return True
    soft_patterns = (
        "experience with docker",
        "experience with kubernetes",
        "database management in your previous",
        "reliability and availability of cloud-based",
        "tell us about your experience with",
        "tell me about your experience with",
        "how would you leverage your experience",
        "design a scalable approach for",
        "design a scalable approach to",
    )
    if any(p in q for p in soft_patterns):
        return True
    return False


def _dossier_anchor_bundles(dossier: dict, limit: int = 5) -> list:
    """
    Self-contained anchor bundles — project + artifact from the SAME source.
    Avoids mashing unrelated highlights into one example question.
    """
    d = dossier or {}
    bundles = []
    seen_projects = set()

    def _add(company, project, artifact, tool_or_method=""):
        project_key = (project or "").strip().lower()[:60]
        if project_key and project_key in seen_projects:
            return
        if project_key:
            seen_projects.add(project_key)
        if not (project or artifact or company):
            return
        bundles.append({
            "company": _shorten_text((company or "").strip(), 60) or "their employer",
            "project": _shorten_text((project or "").strip(), 80) or "a key initiative",
            "artifact": _shorten_text((artifact or "").strip(), 120) or project or "their work",
            "tool_or_method": _shorten_text((tool_or_method or "").strip(), 40),
        })

    for anchor in d.get("resume_anchors") or []:
        if not isinstance(anchor, dict):
            continue
        tech = anchor.get("tech") or []
        tool = tech[0] if isinstance(tech, list) and tech else ""
        actions = anchor.get("actions") or []
        artifact = actions[0] if isinstance(actions, list) and actions else ""
        _add(anchor.get("company"), anchor.get("project"), artifact, tool)

    for proj in d.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        tech = proj.get("tech") or []
        tool = tech[0] if isinstance(tech, list) and tech else ""
        _add(
            (d.get("companies") or [""])[0] if d.get("companies") else "",
            proj.get("name"),
            _entry_highlights_artifact(proj),
            tool,
        )

    for exp in d.get("experience") or []:
        if not isinstance(exp, dict):
            continue
        tech = exp.get("tech") or []
        tool = tech[0] if isinstance(tech, list) and tech else ""
        _add(exp.get("company"), exp.get("title"), _entry_highlights_artifact(exp), tool)

    return bundles[:limit]


def _dossier_anchor_assignment_block(dossier: dict) -> str:
    """Prompt block listing resume anchors the model must distribute across questions."""
    bundles = _dossier_anchor_bundles(dossier, limit=12)
    if not bundles:
        return ""
    lines = [
        "RESUME ANCHOR POOL (assign questions across these; reuse only after all are used once):"
    ]
    for i, b in enumerate(bundles, 1):
        lines.append(
            f"  {i}. {b['project']} @ {b['company']} — {b['artifact']}"
        )
    gaps = [g for g in (dossier or {}).get("gap_skills") or [] if isinstance(g, str) and g.strip()]
    if gaps:
        lines.append(
            "Gap skills (transfer-only, never as past experience): "
            + ", ".join(gaps[:8])
        )
    return "\n".join(lines) + "\n"


def _first_nonempty(*values):
    for v in values:
        if isinstance(v, str) and v.strip():
            return _shorten_text(v.strip(), 80)
        if isinstance(v, list) and v:
            for item in v:
                if isinstance(item, str) and item.strip():
                    return _shorten_text(item.strip(), 80)
                if isinstance(item, dict):
                    for key in ("name", "project", "company", "title", "description", "highlights", "actions"):
                        inner = item.get(key)
                        if isinstance(inner, list) and inner:
                            s = str(inner[0]).strip()
                            if s:
                                return _shorten_text(s, 80)
                        if isinstance(inner, str) and inner.strip():
                            return _shorten_text(inner.strip(), 80)
    return ""


def _dossier_example_snippets(dossier: dict) -> dict:
    """
    Pull real anchors from THIS dossier for prompt examples.
    Uses self-contained bundles so examples never mash unrelated projects.
    """
    d = dossier or {}
    bundles = _dossier_anchor_bundles(d, limit=5)
    a = bundles[0] if bundles else {
        "company": "their employer",
        "project": "a key initiative from the resume",
        "artifact": "a concrete outcome they owned",
        "tool_or_method": "a method or tool from the resume",
    }
    b = bundles[1] if len(bundles) > 1 else a

    responsibilities = d.get("responsibilities") or []
    must_haves = d.get("must_have_skills") or []
    gaps = d.get("gap_skills") or []
    bridges = d.get("transferable_bridges") or []

    jd_need = _first_nonempty(
        responsibilities[0] if responsibilities else "",
        must_haves[0] if must_haves else "",
        d.get("job_title") or "",
        "a core responsibility from the JD",
    )
    gap = _first_nonempty(gaps[0] if gaps else "", "a JD skill not strong on the resume")
    bridge = _first_nonempty(
        bridges[0] if bridges else "",
        f"{a.get('artifact')} -> {jd_need}",
    )
    job_title = _first_nonempty(d.get("job_title") or "", "this role")
    domain = _first_nonempty(d.get("domain") or "", "general")

    return {
        "company": a["company"],
        "project": a["project"],
        "artifact": a["artifact"],
        "tool_or_method": a.get("tool_or_method") or "a method from the resume",
        "project_b": b["project"],
        "artifact_b": b["artifact"],
        "company_b": b["company"],
        "jd_need": jd_need,
        "gap": gap,
        "bridge": bridge,
        "job_title": job_title,
        "domain": domain,
        "bundles": bundles,
    }


def _blend_weight_guidance(blend_pct_resume: int = 50, blend_pct_jd: int = 50) -> str:
    """
    Construct clear, actionable LLM instructions for question framing based on blend weights.
    """
    r_pct = 50 if blend_pct_resume is None else int(blend_pct_resume)
    j_pct = 50 if blend_pct_jd is None else int(blend_pct_jd)

    if j_pct > r_pct:
        return (
            f"WEIGHTING RULE (CRITICAL - {j_pct}% Job Description / {r_pct}% Resume):\n"
            f"- Primary Subject ({j_pct}% weight): Every question MUST center around a specific Job Description expectation, "
            f"duty, must-have skill, key tool, or responsibility from the dossier (responsibilities, jd_highlights, must_have_skills).\n"
            f"- Secondary Subject ({r_pct}% weight): Bring in candidate's resume experience (resume_anchors, experience, projects) secondarily, "
            f"asking how their past work equips them to address that specific JD requirement/scenario.\n"
            f"- Framing: Lead with the JD requirement/challenge first, then connect to candidate's past work. "
            f"Do NOT make candidate's past project the main subject; make the JD requirement the main subject."
        )
    elif r_pct > j_pct:
        return (
            f"WEIGHTING RULE (CRITICAL - {r_pct}% Resume / {j_pct}% Job Description):\n"
            f"- Primary Subject ({r_pct}% weight): Every question MUST center around a specific past project, company, artifact, or tool "
            f"from the candidate's resume (resume_anchors, experience, projects).\n"
            f"- Secondary Subject ({j_pct}% weight): Connect to a JD expectation secondarily to aim the probe toward role relevance.\n"
            f"- Framing: Lead with candidate's past project first, and probe how that past experience aligns with a JD expectation."
        )
    else:
        return (
            f"WEIGHTING RULE ({r_pct}% Resume / {j_pct}% Job Description):\n"
            f"- Balanced Focus: Give equal weight to candidate's past work (resume_anchor) and the Job Description expectation.\n"
            f"- Framing: Seamlessly blend one resume anchor with one JD expectation in each question."
        )


def _dossier_dynamic_examples_block(
    dossier: dict,
    mode: str = "core",
    blend_pct_resume: int = 50,
    blend_pct_jd: int = 50,
) -> str:
    """Universal BAD examples + GOOD examples grounded in THIS dossier."""
    s = _dossier_example_snippets(dossier)
    domain_line = ""
    if s["domain"] and s["domain"] != "general":
        domain_line = (
            f"\nRole domain hint from dossier: {s['domain']}. "
            "Match interview style to that domain (do not force unrelated jargon).\n"
        )
    bundle_lines = []
    for i, bundle in enumerate(s.get("bundles") or [], 1):
        bundle_lines.append(
            f"  Anchor {i}: company={bundle.get('company')!r}, "
            f"project={bundle.get('project')!r}, "
            f"artifact={bundle.get('artifact')!r}"
        )
    bundle_block = "\n".join(bundle_lines) if bundle_lines else ""

    b_res = 50 if blend_pct_resume is None else int(blend_pct_resume)
    b_jd = 50 if blend_pct_jd is None else int(blend_pct_jd)
    is_jd_heavy_blend = mode in ("blend", "hybrid") and b_jd > b_res

    if is_jd_heavy_blend:
        examples_section = f"""
BEGINNER (JD-primary walkthrough — lead with JD expectation):
- BAD: "Walk through {s['project']} at {s['company']}." (too resume-heavy for {blend_pct_jd}% JD weight)
- GOOD: "Our role requires {s['jd_need']}. How does your experience with {s['project']} at {s['company']} demonstrate your ability to deliver this?"

MEDIUM (JD-primary mechanism / challenge — lead with JD requirement):
- BAD: "On {s['project']}, what failure mode worried you most?" (ignores the {blend_pct_jd}% JD weight)
- GOOD: "For this role's key responsibility of {s['jd_need']}, what specific approach would you take given your past work on {s['artifact_b']} at {s['company_b']}?"

HARD (JD-primary judgment & tradeoffs — lead with JD constraint/goal):
- BAD: "Given {s['project']} at {s['company']}, what would you change?" (resume-heavy framing)
- GOOD: "In this role, you will face {s['jd_need']}. Given your background with {s['project']} at {s['company']}, what tradeoffs would you navigate to meet this requirement?"
"""
    else:
        examples_section = f"""
BEGINNER (concrete walkthrough — pick ONE anchor bundle):
- Must name a specific project/outcome from a single anchor (not a bare skill label).
- BAD: "Tell us about your experience with {s['tool_or_method']}."
- BAD: Mixing two anchors: "On {s['project']}, how did you approach {s['artifact_b']}?" (if they are different work)
- GOOD: "Walk through {s['project']} at {s['company']} — what did you own and what changed?"
- GOOD: "Regarding {s['artifact']} at {s['company']}, what did you personally build and what was the result?"

MEDIUM (mechanism / failure / measurement — ONE anchor only):
- Ask how/why, ownership, what broke, or what you measured on that same anchor.
- Link to a JD expectation from the dossier.
- BAD: "Describe a time you faced a challenge at work."
- BAD: "What challenges did you face integrating {s['gap']}?" (gap_skill — invents past use)
- GOOD: "On {s['project']}, what failure mode worried you most in production and how did you mitigate it?"
- GOOD: "For {s['artifact_b']} at {s['company_b']}, how did you measure success and what would you change for {s['jd_need']}?"

HARD (judgment for THIS role — resume anchor + JD need; gap skills as transfer only):
- Apply ONE concrete past anchor to this role's constraints; ask tradeoffs and what they would change.
- BAD: "How would you design a scalable approach for {s['job_title']}?"
- BAD: "Given your experience with {s['gap']}..." (gap must NOT be claimed as past experience)
- GOOD: "Given {s['project']} at {s['company']}, what would you change to meet this role's need for {s['jd_need']} — and why?"
- GOOD: "You may not list {s['gap']} strongly; given {s['artifact_b']}, how would you ramp up for that JD expectation?"
"""

    return f"""{domain_line}
Use ONE anchor bundle per question — do NOT combine project from anchor A with outcome from anchor B.
Self-contained resume anchors from THIS dossier:
{bundle_block}
- JD expectation: {s['jd_need']}
- Gap / stretch skill (transfer only, never as past experience): {s['gap']}
{examples_section}"""


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
    blend_rule = _blend_weight_guidance(blend_pct_resume, blend_pct_jd)
    mode_block = {
        "core": (
            "MODE: core (resume-primary).\n"
            "About 70% resume grounding, 30% JD alignment.\n"
            "Focus mostly on resume experience/projects; use JD to aim the probe at role expectations."
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
            f"{blend_rule}\n"
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
            f"{blend_rule}\n"
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


def _exclude_questions_block(exclude_questions) -> str:
    if not exclude_questions:
        return ""
    lines = []
    for i, q in enumerate(exclude_questions[:40], 1):
        text = (q if isinstance(q, str) else (q.get("question") or "")).strip()
        if text:
            lines.append(f"{i}. {text}")
    if not lines:
        return ""
    return (
        "\nALREADY KEPT QUESTIONS (do NOT repeat, rephrase, or reuse the same "
        "story/project/tech theme):\n"
        + "\n".join(lines)
        + "\n"
    )


def _batch_mode_instructions(
    mode,
    resume_pct=50,
    jd_pct=50,
    blend_pct_resume=50,
    blend_pct_jd=50,
) -> str:
    """Mode-specific rules for one-call batch prompts (domain-agnostic)."""
    blend_rule = _blend_weight_guidance(blend_pct_resume, blend_pct_jd)
    return {
        "core": (
            "MODE: core (resume-primary).\n"
            "About 70% resume grounding, 30% JD alignment.\n"
            "Focus mostly on resume experience/projects; use JD to aim the probe at role expectations."
        ),
        "blend": (
            f"MODE: blend ({blend_pct_resume}% resume / {blend_pct_jd}% JD per question).\n"
            f"{blend_rule}\n"
            "EVERY question must meaningfully combine one resume_anchor with one JD expectation "
            "(prefer overlap_skills; use gap_skills only as transfer tied to closest experience)."
        ),
        "split": (
            f"MODE: split — two buckets in ONE response.\n"
            f"- resume bucket (~{resume_pct}%): ground deeply in resume experience/projects/tools; "
            "briefly connect to a JD expectation.\n"
            f"- jd bucket (~{jd_pct}%): probe JD must-haves/responsibilities, ALWAYS grounded in "
            "closest resume overlap or a fair gap tied to nearest experience. "
            "Do NOT ask generic textbook JD theory."
        ),
        "hybrid": (
            "MODE: hybrid — three buckets in ONE response.\n"
            f"- resume bucket: deep resume probes; still name a JD expectation for relevance.\n"
            f"- jd bucket: JD expectations grounded in closest resume overlap or acknowledged gap — "
            "not textbook quizzes.\n"
            f"- blend bucket ({blend_pct_resume}% resume / {blend_pct_jd}% JD):\n"
            f"  {blend_rule}\n"
            "  each question must integrate both a resume_anchor and a JD expectation."
        ),
    }.get(mode, "MODE: core.")


def _levels_schema_block(b, m, h) -> str:
    return f"""Return ONLY one JSON object with exactly these keys and EXACTLY these counts:
- "beginner": array of EXACTLY {b} objects
- "medium": array of EXACTLY {m} objects
- "hard": array of EXACTLY {h} objects

Each object shape:
{{"question":"...","resume_anchor":"short string","jd_anchor":"short string"}}

resume_anchor and jd_anchor MUST be plain short strings (not objects/arrays).
If a count is 0, return an empty array for that key.
Raw JSON object only. No markdown fences. No commentary."""


def _nested_levels_line(name, dist) -> str:
    b, m, h = int(dist[0]), int(dist[1]), int(dist[2])
    return (
        f'- "{name}": object with "beginner" (EXACTLY {b}), '
        f'"medium" (EXACTLY {m}), "hard" (EXACTLY {h})'
    )


def _split_schema_block(resume_dist, jd_dist) -> str:
    return f"""Return ONLY one JSON object with exactly these top-level keys:
{_nested_levels_line("resume", resume_dist)}
{_nested_levels_line("jd", jd_dist)}

Each question object shape:
{{"question":"...","resume_anchor":"short string","jd_anchor":"short string"}}

resume_anchor and jd_anchor MUST be plain short strings (not objects/arrays).
If a count is 0, return an empty array for that key.
Raw JSON object only. No markdown fences. No commentary."""


def _hybrid_schema_block(resume_dist, jd_dist, blend_dist) -> str:
    return f"""Return ONLY one JSON object with exactly these top-level keys:
{_nested_levels_line("resume", resume_dist)}
{_nested_levels_line("jd", jd_dist)}
{_nested_levels_line("blend", blend_dist)}

Each question object shape:
{{"question":"...","resume_anchor":"short string","jd_anchor":"short string"}}

resume_anchor and jd_anchor MUST be plain short strings (not objects/arrays).
If a count is 0, return an empty array for that key.
Raw JSON object only. No markdown fences. No commentary."""


def _build_mode_batch_prompt(
    job_title,
    dossier,
    mode="core",
    beginner_count=0,
    medium_count=0,
    hard_count=0,
    resume_dist=None,
    jd_dist=None,
    blend_dist=None,
    resume_pct=50,
    jd_pct=50,
    blend_pct_resume=50,
    blend_pct_jd=50,
    exclude_questions=None,
    only_missing=None,
    schema=None,
):
    """
    One-call batch prompt for core/blend (flat levels) or split/hybrid (nested buckets).
    only_missing: flat {{beginner,medium,hard}} or nested {{resume/jd/blend: {{...}}}}.
    """
    schema = schema or ("levels" if mode in ("core", "blend") else mode)
    dossier_blob = _dossier_json(dossier)
    exclude_block = _exclude_questions_block(exclude_questions)
    examples_block = _dossier_dynamic_examples_block(
        dossier or {},
        mode=mode,
        blend_pct_resume=blend_pct_resume,
        blend_pct_jd=blend_pct_jd,
    )
    anchor_block = _dossier_anchor_assignment_block(dossier or {})
    mode_block = _batch_mode_instructions(
        mode, resume_pct, jd_pct, blend_pct_resume, blend_pct_jd
    )

    if schema == "levels":
        if only_missing and isinstance(only_missing, dict) and "beginner" in only_missing:
            b = int(only_missing.get("beginner") or 0)
            m = int(only_missing.get("medium") or 0)
            h = int(only_missing.get("hard") or 0)
        else:
            b, m, h = beginner_count, medium_count, hard_count
        count_contract = (
            f"MANDATORY COUNTS: beginner={b}, medium={m}, hard={h}. "
            "Your JSON is INVALID if any array has a different length. "
            "Do not return fewer items to avoid repetition — write distinct questions instead."
        )
        schema_block = _levels_schema_block(b, m, h)
    elif schema == "split":
        if only_missing and isinstance(only_missing, dict) and "resume" in only_missing:
            rd = only_missing.get("resume") or {}
            jd = only_missing.get("jd") or {}
            resume_dist = [
                int(rd.get("beginner") or 0),
                int(rd.get("medium") or 0),
                int(rd.get("hard") or 0),
            ]
            jd_dist = [
                int(jd.get("beginner") or 0),
                int(jd.get("medium") or 0),
                int(jd.get("hard") or 0),
            ]
        resume_dist = list(resume_dist or [0, 0, 0])
        jd_dist = list(jd_dist or [0, 0, 0])
        count_contract = (
            f"MANDATORY NESTED COUNTS: resume beginner/medium/hard="
            f"{resume_dist[0]}/{resume_dist[1]}/{resume_dist[2]}; "
            f"jd beginner/medium/hard={jd_dist[0]}/{jd_dist[1]}/{jd_dist[2]}. "
            "Your JSON is INVALID if any array length differs. "
            "Do not return fewer items to avoid repetition."
        )
        schema_block = _split_schema_block(resume_dist, jd_dist)
    else:  # hybrid
        if only_missing and isinstance(only_missing, dict) and "resume" in only_missing:
            rd = only_missing.get("resume") or {}
            jd = only_missing.get("jd") or {}
            bd = only_missing.get("blend") or {}
            resume_dist = [
                int(rd.get("beginner") or 0),
                int(rd.get("medium") or 0),
                int(rd.get("hard") or 0),
            ]
            jd_dist = [
                int(jd.get("beginner") or 0),
                int(jd.get("medium") or 0),
                int(jd.get("hard") or 0),
            ]
            blend_dist = [
                int(bd.get("beginner") or 0),
                int(bd.get("medium") or 0),
                int(bd.get("hard") or 0),
            ]
        resume_dist = list(resume_dist or [0, 0, 0])
        jd_dist = list(jd_dist or [0, 0, 0])
        blend_dist = list(blend_dist or [0, 0, 0])
        count_contract = (
            f"MANDATORY NESTED COUNTS: resume={resume_dist[0]}/{resume_dist[1]}/{resume_dist[2]}; "
            f"jd={jd_dist[0]}/{jd_dist[1]}/{jd_dist[2]}; "
            f"blend={blend_dist[0]}/{blend_dist[1]}/{blend_dist[2]}. "
            "Your JSON is INVALID if any array length differs. "
            "Do not return fewer items to avoid repetition."
        )
        schema_block = _hybrid_schema_block(resume_dist, jd_dist, blend_dist)

    return f"""You are an expert interviewer writing live interview questions for **{job_title}**.

{_shared_interview_contract_text()}

{mode_block}
Generate ALL difficulties (and buckets if applicable) in ONE response.
Depth MUST increase beginner → medium → hard within each bucket.
Match the domain of THIS resume and JD — do not force unrelated industry jargon
(tech, business, creative, operations, etc. — follow the dossier domain).

{count_contract}

{anchor_block}
{examples_block}
UNIQUENESS (strict — enforced by you, not post-processing):
- Every question MUST be distinct: different anchor, angle, or JD tie-in. No near-paraphrases.
- Each question uses ONE anchor bundle only (do not mix unrelated project + outcome).
- Spread questions across the RESUME ANCHOR POOL before reusing any project.
- gap_skills: NEVER as past experience — only transfer ("how would you approach…").
- Soft skills (communication, teamwork, Agile) in at most ONE question total across the whole batch.
- beginner = walkthrough; medium = mechanism/failure/measurement; hard = tradeoffs/judgment for THIS role.
{exclude_block}
CANDIDATE/ROLE DOSSIER (use ONLY this; do not invent employers/projects not listed):
{dossier_blob}

{schema_block}"""


def _build_core_batch_prompt(
    job_title,
    dossier,
    beginner_count,
    medium_count,
    hard_count,
    exclude_questions=None,
    only_missing=None,
):
    """Backward-compatible wrapper for core flat-level batch prompts."""
    return _build_mode_batch_prompt(
        job_title,
        dossier,
        mode="core",
        beginner_count=beginner_count,
        medium_count=medium_count,
        hard_count=hard_count,
        exclude_questions=exclude_questions,
        only_missing=only_missing,
        schema="levels",
    )


def _parse_level_batch_from_dict(parsed, beginner_count, medium_count, hard_count):
    """Normalize beginner/medium/hard arrays from a dict (or empty)."""
    if not isinstance(parsed, dict):
        return [], [], []
    beginner = _normalize_question_items(parsed.get("beginner") or [], "beginner", 1)
    medium = _normalize_question_items(parsed.get("medium") or [], "medium", 3)
    hard = _normalize_question_items(parsed.get("hard") or [], "hard", 5)
    return (
        beginner[:beginner_count] if beginner_count else [],
        medium[:medium_count] if medium_count else [],
        hard[:hard_count] if hard_count else [],
    )


def _parse_flat_array_by_difficulty(raw, beginner_count, medium_count, hard_count):
    arr = extract_json_array(raw) if raw else []
    beginner, medium, hard = [], [], []
    for item in arr or []:
        if not isinstance(item, dict):
            continue
        level = (item.get("difficulty") or item.get("level") or "").strip().lower()
        if level in ("beginner", "easy", "basic"):
            beginner.append(item)
        elif level in ("medium", "intermediate", "mid"):
            medium.append(item)
        elif level in ("hard", "expert", "advanced"):
            hard.append(item)
    return (
        _normalize_question_items(beginner, "beginner", 1)[:beginner_count],
        _normalize_question_items(medium, "medium", 3)[:medium_count],
        _normalize_question_items(hard, "hard", 5)[:hard_count],
    )


def _parse_core_batch_response(raw, beginner_count, medium_count, hard_count):
    """Parse batched core/blend JSON into normalized per-level lists."""
    parsed = _parse_llm_json_object(raw)
    if not isinstance(parsed, dict):
        return _parse_flat_array_by_difficulty(raw, beginner_count, medium_count, hard_count)
    # Nested mistaken response: flatten resume/jd/blend if present without top-level levels
    if (
        parsed.get("beginner") is None
        and parsed.get("medium") is None
        and parsed.get("hard") is None
        and any(k in parsed for k in ("resume", "jd", "blend"))
    ):
        return _flatten_bucket_levels(parsed, beginner_count, medium_count, hard_count)
    return _parse_level_batch_from_dict(parsed, beginner_count, medium_count, hard_count)


def _flatten_bucket_levels(parsed, beginner_count, medium_count, hard_count):
    """Merge nested resume/jd/blend level arrays into flat lists (cap at targets)."""
    beginner, medium, hard = [], [], []
    for key in ("resume", "jd", "blend"):
        bucket = parsed.get(key)
        if not isinstance(bucket, dict):
            continue
        b, m, h = _parse_level_batch_from_dict(bucket, 999, 999, 999)
        beginner.extend(b)
        medium.extend(m)
        hard.extend(h)
    return (
        beginner[:beginner_count] if beginner_count else [],
        medium[:medium_count] if medium_count else [],
        hard[:hard_count] if hard_count else [],
    )


def _parse_split_batch_response(raw, resume_dist, jd_dist):
    """Parse nested split JSON; return flattened beginner/medium/hard lists."""
    resume_dist = list(resume_dist or [0, 0, 0])
    jd_dist = list(jd_dist or [0, 0, 0])
    target_b = resume_dist[0] + jd_dist[0]
    target_m = resume_dist[1] + jd_dist[1]
    target_h = resume_dist[2] + jd_dist[2]

    parsed = _parse_llm_json_object(raw)
    if not isinstance(parsed, dict):
        return _parse_flat_array_by_difficulty(raw, target_b, target_m, target_h)

    # Flat levels fallback
    if parsed.get("beginner") is not None or parsed.get("medium") is not None:
        return _parse_level_batch_from_dict(parsed, target_b, target_m, target_h)

    rb, rm, rh = _parse_level_batch_from_dict(
        parsed.get("resume") or {}, resume_dist[0], resume_dist[1], resume_dist[2]
    )
    jb, jm, jh = _parse_level_batch_from_dict(
        parsed.get("jd") or {}, jd_dist[0], jd_dist[1], jd_dist[2]
    )
    return (
        (rb + jb)[:target_b],
        (rm + jm)[:target_m],
        (rh + jh)[:target_h],
    )


def _parse_hybrid_batch_response(raw, resume_dist, jd_dist, blend_dist):
    """Parse nested hybrid JSON; return flattened beginner/medium/hard lists."""
    resume_dist = list(resume_dist or [0, 0, 0])
    jd_dist = list(jd_dist or [0, 0, 0])
    blend_dist = list(blend_dist or [0, 0, 0])
    target_b = resume_dist[0] + jd_dist[0] + blend_dist[0]
    target_m = resume_dist[1] + jd_dist[1] + blend_dist[1]
    target_h = resume_dist[2] + jd_dist[2] + blend_dist[2]

    parsed = _parse_llm_json_object(raw)
    if not isinstance(parsed, dict):
        return _parse_flat_array_by_difficulty(raw, target_b, target_m, target_h)

    if parsed.get("beginner") is not None or parsed.get("medium") is not None:
        return _parse_level_batch_from_dict(parsed, target_b, target_m, target_h)

    rb, rm, rh = _parse_level_batch_from_dict(
        parsed.get("resume") or {}, resume_dist[0], resume_dist[1], resume_dist[2]
    )
    jb, jm, jh = _parse_level_batch_from_dict(
        parsed.get("jd") or {}, jd_dist[0], jd_dist[1], jd_dist[2]
    )
    bb, bm, bh = _parse_level_batch_from_dict(
        parsed.get("blend") or {}, blend_dist[0], blend_dist[1], blend_dist[2]
    )
    return (
        (rb + jb + bb)[:target_b],
        (rm + jm + bm)[:target_m],
        (rh + jh + bh)[:target_h],
    )


def _batch_json_looks_usable(parsed) -> bool:
    if not isinstance(parsed, dict):
        return False
    if (
        parsed.get("beginner") is not None
        or parsed.get("medium") is not None
        or parsed.get("hard") is not None
    ):
        return True
    for key in ("resume", "jd", "blend"):
        bucket = parsed.get(key)
        if isinstance(bucket, dict) and (
            bucket.get("beginner") is not None
            or bucket.get("medium") is not None
            or bucket.get("hard") is not None
        ):
            return True
    return False


def _call_core_batch_llm(prompt, model, label="core_batch"):
    """One batched question call with high output budget. Returns (raw|None, error|None)."""
    print(
        f"[INFO] Question batch LLM start ({label}): "
        f"max_tokens={QUESTION_BATCH_MAX_TOKENS} temperature={QUESTION_BATCH_TEMPERATURE}"
    )
    last_error = None
    best_raw = None
    for attempt in range(QUESTION_GEN_MAX_RETRIES):
        try:
            response = try_ollama_chat(
                prompt.strip(),
                model=model,
                max_tokens=QUESTION_BATCH_MAX_TOKENS,
                temperature=QUESTION_BATCH_TEMPERATURE,
            )
            raw = (response.get("message") or {}).get("content") or ""
            usage = response.get("usage") or {}
            out_tok = usage.get("output_tokens")
            parsed = _parse_llm_json_object(raw)
            if _batch_json_looks_usable(parsed):
                print(
                    f"[INFO] Question batch JSON ok ({label}) "
                    f"attempt {attempt + 1}/{QUESTION_GEN_MAX_RETRIES}"
                    + (f" output_tokens={out_tok}" if out_tok is not None else "")
                )
                return raw, None
            # Accept flat array fallback as usable raw
            arr = extract_json_array(raw)
            if arr:
                print(
                    f"[INFO] Question batch array fallback ok ({label}) "
                    f"attempt {attempt + 1}/{QUESTION_GEN_MAX_RETRIES}"
                )
                return raw, None
            last_error = "invalid_or_empty_json"
            best_raw = raw or best_raw
            preview = (raw or "").replace("\n", " ")[:160]
            print(
                f"[WARN] Question batch unusable JSON ({label}) "
                f"attempt {attempt + 1}/{QUESTION_GEN_MAX_RETRIES} "
                f"raw_len={len(raw or '')} preview={preview!r}"
            )
        except Exception as e:
            last_error = str(e)
            print(
                f"[WARN] Question batch LLM failed ({label}) "
                f"attempt {attempt + 1}/{QUESTION_GEN_MAX_RETRIES}: {e}"
            )
    return best_raw, last_error


def _missing_nested_for_refill(need_b, need_m, need_h, schema):
    """Put all missing level counts into the resume bucket for nested refill rounds."""
    levels = {"beginner": need_b, "medium": need_m, "hard": need_h}
    empty = {"beginner": 0, "medium": 0, "hard": 0}
    if schema == "split":
        return {"resume": levels, "jd": dict(empty)}
    return {"resume": levels, "jd": dict(empty), "blend": dict(empty)}


def _generate_batched_levels(
    job_title,
    dossier,
    beginner_count,
    medium_count,
    hard_count,
    model,
    mode="core",
    label_prefix="core_batch",
    blend_pct_resume=50,
    blend_pct_jd=50,
):
    """
    Shared exact-count runner for flat beginner/medium/hard schemas (core + blend).
    Refills until counts met or max rounds exhausted. No heuristic dedupe.
    """
    beginner_count = max(0, int(beginner_count or 0))
    medium_count = max(0, int(medium_count or 0))
    hard_count = max(0, int(hard_count or 0))
    if beginner_count + medium_count + hard_count <= 0:
        return {"beginner": [], "medium": [], "hard": []}

    print(
        f"[INFO] Generating {mode} questions in one batch (dossier-backed)... "
        f"counts beginner={beginner_count} medium={medium_count} hard={hard_count}"
    )

    beginner_qs: list = []
    medium_qs: list = []
    hard_qs: list = []

    for round_num in range(QUESTION_BATCH_MAX_REFILL_ROUNDS):
        need_b = max(0, beginner_count - len(beginner_qs))
        need_m = max(0, medium_count - len(medium_qs))
        need_h = max(0, hard_count - len(hard_qs))
        if not need_b and not need_m and not need_h:
            break

        if round_num == 0:
            req_b, req_m, req_h = beginner_count, medium_count, hard_count
            label = label_prefix
            exclude = None
            only_missing = None
        else:
            req_b, req_m, req_h = need_b, need_m, need_h
            label = f"{label_prefix}_refill_{round_num}"
            exclude = beginner_qs + medium_qs + hard_qs
            only_missing = {"beginner": need_b, "medium": need_m, "hard": need_h}
            print(
                f"[INFO] {mode} batch refill round {round_num}: "
                f"beginner={need_b} medium={need_m} hard={need_h}"
            )

        prompt = _build_mode_batch_prompt(
            job_title,
            dossier,
            mode=mode,
            beginner_count=beginner_count,
            medium_count=medium_count,
            hard_count=hard_count,
            blend_pct_resume=blend_pct_resume,
            blend_pct_jd=blend_pct_jd,
            exclude_questions=exclude,
            only_missing=only_missing,
            schema="levels",
        )
        raw, err = _call_core_batch_llm(prompt, model, label=label)
        if not raw:
            print(f"[ERROR] {mode} batch question generation failed ({label}): {err}")
            break

        rb, rm, rh = _parse_core_batch_response(raw, req_b, req_m, req_h)
        print(
            f"[INFO] {label} parsed: "
            f"beginner={len(rb)}/{req_b} medium={len(rm)}/{req_m} hard={len(rh)}/{req_h}"
        )

        beginner_qs = (beginner_qs + rb)[:beginner_count]
        medium_qs = (medium_qs + rm)[:medium_count]
        hard_qs = (hard_qs + rh)[:hard_count]

    final_b, final_m, final_h = len(beginner_qs), len(medium_qs), len(hard_qs)
    if final_b < beginner_count or final_m < medium_count or final_h < hard_count:
        print(
            f"[WARN] {mode} question counts short after {QUESTION_BATCH_MAX_REFILL_ROUNDS} rounds: "
            f"beginner={final_b}/{beginner_count} "
            f"medium={final_m}/{medium_count} "
            f"hard={final_h}/{hard_count}"
        )
    else:
        print(
            f"[INFO] {mode} question counts satisfied: "
            f"beginner={final_b} medium={final_m} hard={final_h}"
        )

    print(f"[DEBUG] Beginner: {final_b} | Medium: {final_m} | Hard: {final_h}")

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }


def _generate_batched_buckets(
    job_title,
    dossier,
    beginner_count,
    medium_count,
    hard_count,
    model,
    mode,
    label_prefix,
    resume_dist,
    jd_dist,
    blend_dist=None,
    resume_pct=50,
    jd_pct=50,
    blend_pct_resume=50,
    blend_pct_jd=50,
):
    """
    Shared exact-count runner for nested split/hybrid schemas.
    Flattened beginner/medium/hard must match requested totals.
    """
    resume_dist = list(resume_dist or [0, 0, 0])
    jd_dist = list(jd_dist or [0, 0, 0])
    blend_dist = list(blend_dist or [0, 0, 0]) if mode == "hybrid" else None
    schema = "hybrid" if mode == "hybrid" else "split"

    beginner_count = resume_dist[0] + jd_dist[0] + (blend_dist[0] if blend_dist else 0)
    medium_count = resume_dist[1] + jd_dist[1] + (blend_dist[1] if blend_dist else 0)
    hard_count = resume_dist[2] + jd_dist[2] + (blend_dist[2] if blend_dist else 0)

    beginner_qs: list = []
    medium_qs: list = []
    hard_qs: list = []

    for round_num in range(QUESTION_BATCH_MAX_REFILL_ROUNDS):
        need_b = max(0, beginner_count - len(beginner_qs))
        need_m = max(0, medium_count - len(medium_qs))
        need_h = max(0, hard_count - len(hard_qs))
        if not need_b and not need_m and not need_h:
            break

        if round_num == 0:
            label = label_prefix
            exclude = None
            only_missing = None
            req_rd, req_jd, req_bd = resume_dist, jd_dist, blend_dist
        else:
            label = f"{label_prefix}_refill_{round_num}"
            exclude = beginner_qs + medium_qs + hard_qs
            only_missing = _missing_nested_for_refill(need_b, need_m, need_h, schema)
            req_rd = [
                only_missing["resume"]["beginner"],
                only_missing["resume"]["medium"],
                only_missing["resume"]["hard"],
            ]
            req_jd = [0, 0, 0]
            req_bd = [0, 0, 0] if mode == "hybrid" else None
            print(
                f"[INFO] {mode} batch refill round {round_num}: "
                f"beginner={need_b} medium={need_m} hard={need_h}"
            )

        prompt = _build_mode_batch_prompt(
            job_title,
            dossier,
            mode=mode,
            resume_dist=req_rd,
            jd_dist=req_jd,
            blend_dist=req_bd,
            resume_pct=resume_pct,
            jd_pct=jd_pct,
            blend_pct_resume=blend_pct_resume,
            blend_pct_jd=blend_pct_jd,
            exclude_questions=exclude,
            only_missing=only_missing,
            schema=schema,
        )
        raw, err = _call_core_batch_llm(prompt, model, label=label)
        if not raw:
            print(f"[ERROR] {mode} batch question generation failed ({label}): {err}")
            break

        if mode == "hybrid":
            rb, rm, rh = _parse_hybrid_batch_response(raw, req_rd, req_jd, req_bd or [0, 0, 0])
        else:
            rb, rm, rh = _parse_split_batch_response(raw, req_rd, req_jd)

        # Cap additions so we never exceed remaining need this round
        rb = rb[:need_b if round_num else beginner_count]
        rm = rm[:need_m if round_num else medium_count]
        rh = rh[:need_h if round_num else hard_count]
        if round_num == 0:
            rb = rb[:beginner_count]
            rm = rm[:medium_count]
            rh = rh[:hard_count]

        print(
            f"[INFO] {label} parsed: "
            f"beginner={len(rb)} medium={len(rm)} hard={len(rh)}"
        )

        beginner_qs = (beginner_qs + rb)[:beginner_count]
        medium_qs = (medium_qs + rm)[:medium_count]
        hard_qs = (hard_qs + rh)[:hard_count]

    final_b, final_m, final_h = len(beginner_qs), len(medium_qs), len(hard_qs)
    if final_b < beginner_count or final_m < medium_count or final_h < hard_count:
        print(
            f"[WARN] {mode} question counts short after {QUESTION_BATCH_MAX_REFILL_ROUNDS} rounds: "
            f"beginner={final_b}/{beginner_count} "
            f"medium={final_m}/{medium_count} "
            f"hard={final_h}/{hard_count}"
        )
    else:
        print(
            f"[INFO] {mode} question counts satisfied: "
            f"beginner={final_b} medium={final_m} hard={final_h}"
        )

    print(f"[DONE] Final counts -> Beginner: {final_b}, Medium: {final_m}, Hard: {final_h}")

    return {
        "beginner": _strip_internal_question_fields(beginner_qs),
        "medium": _strip_internal_question_fields(medium_qs),
        "hard": _strip_internal_question_fields(hard_qs),
    }


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
    """
    Generate core questions via batched LLM calls (dossier fed once per round).
    Refills until exact per-level counts are met or max rounds exhausted.
    No post-generation heuristic dedupe — quality enforced via prompt only.
    """
    if dossier is None:
        raise ValueError("dossier is required for question generation")

    return _generate_batched_levels(
        job_title,
        dossier,
        beginner_count,
        medium_count,
        hard_count,
        model,
        mode="core",
        label_prefix="core_batch",
    )

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
        raise ValueError("dossier is required for coding question generation")

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
    """Split mode: one nested batch call (resume + jd × all difficulties), then refill."""
    if dossier is None:
        raise ValueError("dossier is required for split question generation")

    beginner_count = max(0, int(beginner_count or 0))
    medium_count = max(0, int(medium_count or 0))
    hard_count = max(0, int(hard_count or 0))
    total = beginner_count + medium_count + hard_count
    if total == 0:
        return {"beginner": [], "medium": [], "hard": []}

    if jd_pct is not None and (resume_pct == 50 or jd_pct != 50):
        jd_total = round(total * (jd_pct / 100))
        resume_total = total - jd_total
    else:
        resume_total = round(total * (resume_pct / 100))
        jd_total = total - resume_total

    # Ensure at least 1 question for non-zero percentage if total allows
    if jd_pct > 0 and jd_total == 0 and total > 0:
        jd_total = 1
        resume_total = max(0, total - 1)
    elif resume_pct > 0 and resume_total == 0 and total > 0:
        resume_total = 1
        jd_total = max(0, total - 1)

    print(f"\n{Fore.BLUE}=== SPLIT MODE DEBUG ==={Style.RESET_ALL}")
    print(f"{Fore.CYAN}[REQUESTED]{Style.RESET_ALL} Resume={resume_pct}% ({resume_total}), JD={jd_pct}% ({jd_total})")

    def distribute(bucket_total, total_count):
        if bucket_total <= 0 or total_count <= 0:
            return (0, 0, 0)
        b = round(bucket_total * (beginner_count / total_count))
        m = round(bucket_total * (medium_count / total_count))
        h = round(bucket_total * (hard_count / total_count))
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

    print(f"{Fore.CYAN}[BALANCED]{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}Resume -> Beginner={resume_dist[0]}, Medium={resume_dist[1]}, Hard={resume_dist[2]}{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}JD     -> Beginner={jd_dist[0]}, Medium={jd_dist[1]}, Hard={jd_dist[2]}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}=========================={Style.RESET_ALL}\n")

    return _generate_batched_buckets(
        job_title,
        dossier,
        beginner_count,
        medium_count,
        hard_count,
        model,
        mode="split",
        label_prefix="split_batch",
        resume_dist=resume_dist,
        jd_dist=jd_dist,
        resume_pct=resume_pct,
        jd_pct=jd_pct,
    )


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
    """Generate blended questions in one multi-difficulty batch (exact counts via refill)."""
    if dossier is None:
        raise ValueError("dossier is required for blend question generation")

    print(f"[INFO] Generating blended questions (Resume {blend_pct_resume}% | JD {blend_pct_jd}%)")

    return _generate_batched_levels(
        job_title,
        dossier,
        beginner_count,
        medium_count,
        hard_count,
        model,
        mode="blend",
        label_prefix="blend_batch",
        blend_pct_resume=blend_pct_resume,
        blend_pct_jd=blend_pct_jd,
    )

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
    One nested batch call; preserves user-requested beginner/medium/hard counts.
    """
    if dossier is None:
        raise ValueError("dossier is required for hybrid question generation")

    beginner_count = max(0, int(beginner_count or 0))
    medium_count = max(0, int(medium_count or 0))
    hard_count = max(0, int(hard_count or 0))
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

    return _generate_batched_buckets(
        job_title,
        dossier,
        beginner_count,
        medium_count,
        hard_count,
        model,
        mode="hybrid",
        label_prefix="hybrid_batch",
        resume_dist=resume_dist,
        jd_dist=jd_dist,
        blend_dist=blend_dist,
        resume_pct=resume_pct,
        jd_pct=jd_pct,
        blend_pct_resume=blend_pct_resume,
        blend_pct_jd=blend_pct_jd,
    )


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
    user_id=None,
    resume_text=None,
):

    """
    Run the resume pipeline with data from frontend instead of config file.

    Hard gate:
    - Regenerate (ids only): load dossier once; miss → fail (no resume rebuild).
    - First build (resume_text / resume_path / skills_list): build dossier; llm_failed → stop
      (no questions). Success → save dossier → generate questions.
    Prefer resume_text from the API to avoid extracting the same file twice.
    Sample answers are deferred to a later stage (even if include_answers=True).
    """
    
    resolved_model = resolve_ollama_model_name()
    import shutil

    for attempt in range(max_retries):
        temp_dir = None
        try:
            print(f"\n[INFO] API Attempt {attempt + 1} of {max_retries}")

            if not split and not blend:
                if (jd_pct is not None and jd_pct != 50) or (resume_pct is not None and resume_pct != 50):
                    split = True
                elif (blend_pct_jd is not None and blend_pct_jd != 50) or (blend_pct_resume is not None and blend_pct_resume != 50):
                    blend = True

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

                print(f"[INFO] Processing for: {job_title}")
                print(f"[INFO] Question counts: {question_counts}")
                print(f"[INFO] Include answers: {include_answers}")
                print(f"[INFO] Ollama model: {resolved_model}")
                print(f"[INFO] Mode: {mode_label} | Split={split} ({resume_pct}%/{jd_pct}%) | Blend={blend}")

                preextracted_resume_text = (resume_text or "").strip()
                resume_text = ""
                candidate_name = "candidate"
                dossier_cache_status = "skip"
                has_source = bool(skills_list) or bool(preextracted_resume_text) or bool(
                    resume_path and os.path.exists(resume_path)
                )

                # Single dossier load — regenerate never re-parses resume/skills.
                can_cache = bool((resume_id or "").strip() and (jd_id or "").strip())
                dossier = None
                if can_cache:
                    dossier = load_dossier(resume_id, jd_id, user_id=user_id)
                    if dossier:
                        dossier_cache_status = "hit"
                        print(
                            f"[INFO] Dossier cache hit resume_id={resume_id} jd_id={jd_id} "
                            "(skipping resume/skills parse)"
                        )
                    else:
                        dossier_cache_status = "miss"
                        print(
                            f"[INFO] Dossier cache miss resume_id={resume_id} jd_id={jd_id}"
                        )
                else:
                    print("[INFO] Dossier cache skipped (missing resume_id or jd_id)")

                if not dossier:
                    if not has_source:
                        return {
                            "success": False,
                            "code": "DOSSIER_MISSING",
                            "error": (
                                "Interview dossier not found for this resume/JD pair. "
                                "Re-run question generation from upload."
                            ),
                        }

                    if skills_list:
                        structured_from_skills = build_structured_data_from_skills(skills_list)
                        if not structured_from_skills or not structured_from_skills.get("skills"):
                            return {
                                "success": False,
                                "error": "Please provide at least one skill (comma-separated).",
                            }
                        skills_list = structured_from_skills.get("skills") or skills_list
                        print(
                            f"[INFO] Building dossier from skills-based profile "
                            f"({len(skills_list)} skills)"
                        )
                    elif preextracted_resume_text:
                        # Already extracted+validated by the API — avoid a second parse.
                        print("[INFO] Building dossier from pre-extracted resume text")
                        resume_text = preextracted_resume_text
                        candidate_name = _candidate_name_from_text(resume_text)
                    elif resume_path and os.path.exists(resume_path):
                        print("[INFO] Building dossier from resume file")
                        resume_text = extract_text_from_resume(resume_path)
                        from common.document_validation import validate_resume_text
                        is_valid_resume, resume_validation_error = validate_resume_text(resume_text)
                        if not is_valid_resume:
                            raise ResumeParseError(resume_validation_error)
                        candidate_name = _candidate_name_from_text(resume_text)
                    else:
                        return {
                            "success": False,
                            "code": "DOSSIER_MISSING",
                            "error": (
                                "Interview dossier not found for this resume/JD pair. "
                                "Re-run question generation from upload."
                            ),
                        }

                    dossier = build_interview_dossier_from_text(
                        resume_text,
                        job_title,
                        job_description,
                        model=resolved_model,
                        skills_list=skills_list,
                    )
                    # Hard gate: never generate questions from a failed dossier.
                    if (dossier or {}).get("source") == "llm_failed":
                        print(
                            "[ERROR] Dossier build failed (source=llm_failed); "
                            "aborting question generation"
                        )
                        return {
                            "success": False,
                            "code": "DOSSIER_BUILD_FAILED",
                            "error": (
                                "Failed to build the interview dossier from your profile. "
                                "No questions were generated. Please retry."
                            ),
                        }
                    if can_cache:
                        saved = save_dossier(
                            resume_id,
                            jd_id,
                            dossier,
                            job_title=job_title,
                            user_id=user_id,
                        )
                        if not saved:
                            return {
                                "success": False,
                                "code": "DOSSIER_BUILD_FAILED",
                                "error": (
                                    "Interview dossier was built but could not be saved. "
                                    "No questions were generated. Please retry."
                                ),
                            }

                structured_data = _stub_structured_from_dossier(
                    dossier, candidate_name, skills_list=skills_list
                )

                # Create temporary output directory (cleaned in finally)
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

                # Read back questions into memory before temp cleanup
                questions = read_questions_from_csv(questions_path)

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
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    print(f"[INFO] Cleaned temp dir: {temp_dir}")
                except Exception as cleanup_err:
                    print(f"[WARN] Temp dir cleanup failed: {cleanup_err}")

