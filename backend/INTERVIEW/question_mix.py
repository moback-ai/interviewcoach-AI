"""Interview question mix planning: domain presets, grounding gates, and count allocation.

Phase 1 module — consumed by question_generation.run_pipeline_from_api in a later phase.
Does not call LLMs; safe for unit tests with static dossier fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

QUESTION_TYPES = ("behavioral", "concepts", "situational", "coding")
INTERVIEW_FOCI = ("technical", "product", "operations", "general")
DEPTH_PROFILES = ("warmup", "balanced", "challenging")
DIFFICULTY_LEVELS = ("beginner", "medium", "hard")

# Ticket percentages; coding zeroed for non-technical roles after normalization.
DOMAIN_PRESETS: dict[str, dict[str, float]] = {
    "technical": {
        "behavioral": 0.45,
        "concepts": 0.30,
        "situational": 0.15,
        "coding": 0.10,
    },
    "product": {
        "behavioral": 0.45,
        "concepts": 0.25,
        "situational": 0.30,
        "coding": 0.00,
    },
    "operations": {
        "behavioral": 0.50,
        "concepts": 0.20,
        "situational": 0.30,
        "coding": 0.00,
    },
    "general": {
        "behavioral": 0.50,
        "concepts": 0.25,
        "situational": 0.25,
        "coding": 0.00,
    },
}

DEPTH_PROFILE_RATIOS: dict[str, dict[str, float]] = {
    "warmup": {"beginner": 0.50, "medium": 0.35, "hard": 0.15},
    "balanced": {"beginner": 0.33, "medium": 0.34, "hard": 0.33},
    "challenging": {"beginner": 0.15, "medium": 0.35, "hard": 0.50},
}

GENERATION_SHORTFALL_PRIORITY: dict[str, tuple[str, ...]] = {
    "behavioral": ("situational", "concepts"),
    "concepts": ("situational", "behavioral"),
    "situational": ("concepts", "behavioral"),
    "coding": ("concepts",),
}

_BUCKET_PRIORITY_FOR_SMALL_TOTALS = ("behavioral", "concepts", "situational", "coding")

_FOCUS_KEYWORD_SCORES: dict[str, tuple[str, ...]] = {
    "technical": (
        "engineer",
        "developer",
        "devops",
        "sre",
        "software",
        "backend",
        "frontend",
        "full stack",
        "fullstack",
        "data scientist",
        "ml ",
        "machine learning",
        "architect",
        "platform",
        "infrastructure",
        "qa automation",
        "embedded",
    ),
    "product": (
        "product manager",
        "product owner",
        "product design",
        "product marketing",
        "pm ",
        " ux",
        " ui ",
        "designer",
        "growth",
        "roadmap",
    ),
    "operations": (
        "operations",
        " ops",
        "compliance",
        "process",
        "supply chain",
        "logistics",
        "program manager",
        "project manager",
        "customer success",
        "support manager",
        "business analyst",
    ),
}

_DOMAIN_FIELD_ALIASES: dict[str, str] = {
    "tech": "technical",
    "technical": "technical",
    "engineering": "technical",
    "software": "technical",
    "product": "product",
    "design": "product",
    "operations": "operations",
    "ops": "operations",
    "business": "operations",
    "general": "general",
}

_CODE_SKILL_HINTS = frozenset(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "go",
        "golang",
        "rust",
        "c++",
        "c#",
        "ruby",
        "php",
        "kotlin",
        "swift",
        "scala",
        "sql",
        "react",
        "node",
        "angular",
        "vue",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
    }
)


@dataclass(frozen=True)
class QuestionPlan:
    """Resolved generation plan for one question batch."""

    total_count: int
    interview_focus: str
    depth_profile: str
    is_technical: bool
    type_counts: dict[str, int]
    type_difficulty: dict[str, dict[str, int]]
    eligibility: dict[str, bool]
    mix_percentages: dict[str, float]
    notices: tuple[str, ...] = field(default_factory=tuple)


def normalize_focus_key(raw: str | None) -> str | None:
    """Map free-text focus/domain labels to a preset key."""
    if not raw or not str(raw).strip():
        return None
    key = str(raw).strip().lower()
    if key in DOMAIN_PRESETS:
        return key
    return _DOMAIN_FIELD_ALIASES.get(key)


def is_technical_role_heuristic(job_title: str = "", job_description: str = "") -> bool:
    """Keyword heuristic for coding eligibility (no LLM)."""
    blob = f"{job_title} {job_description}".lower()
    technical_hits = sum(1 for kw in _FOCUS_KEYWORD_SCORES["technical"] if kw in blob)
    product_hits = sum(1 for kw in _FOCUS_KEYWORD_SCORES["product"] if kw in blob)
    explicit_coding = any(
        token in blob
        for token in (
            "coding interview",
            "leetcode",
            "algorithm",
            "data structure",
            "write code",
            "programming",
        )
    )
    if explicit_coding:
        return True
    return technical_hits >= 2 or (technical_hits >= 1 and product_hits == 0)


def infer_interview_focus(
    dossier: Mapping | None,
    job_title: str = "",
    job_description: str = "",
    is_technical: bool | None = None,
) -> str:
    """Infer interview focus preset from dossier domain + title/JD keywords."""
    dossier = dossier or {}
    domain_key = normalize_focus_key(str(dossier.get("domain") or ""))
    if domain_key:
        return domain_key

    blob = f"{job_title} {job_description}".lower()
    scores = {
        focus: sum(1 for kw in keywords if kw in blob)
        for focus, keywords in _FOCUS_KEYWORD_SCORES.items()
    }
    best_focus, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score > 0:
        return best_focus

    if is_technical is None:
        is_technical = is_technical_role_heuristic(job_title, job_description)
    if is_technical:
        return "technical"
    return "general"


def get_preset_mix(focus_key: str) -> dict[str, float]:
    """Return a copy of the mix percentages for a focus preset."""
    key = normalize_focus_key(focus_key) or "general"
    preset = DOMAIN_PRESETS.get(key, DOMAIN_PRESETS["general"])
    return dict(preset)


def normalize_mix(mix: Mapping[str, float], is_technical: bool) -> dict[str, float]:
    """Zero coding for non-technical roles and renormalize to sum to 1.0."""
    cleaned = {bucket: max(0.0, float(mix.get(bucket, 0.0))) for bucket in QUESTION_TYPES}
    if not is_technical:
        cleaned["coding"] = 0.0
    total = sum(cleaned.values())
    if total <= 0:
        return dict(DOMAIN_PRESETS["general"])
    return {bucket: cleaned[bucket] / total for bucket in QUESTION_TYPES}


def largest_remainder_allocate(
    total: int,
    weights: Mapping[str, float],
    all_keys: Sequence[str] | None = None,
) -> dict[str, int]:
    """Allocate integer counts that sum to total using the largest-remainder method."""
    keys = tuple(all_keys) if all_keys is not None else QUESTION_TYPES
    total = max(0, int(total))
    if total == 0:
        return {bucket: 0 for bucket in keys}

    positive = {k: max(0.0, float(v)) for k, v in weights.items() if float(v) > 0}
    if not positive:
        return {bucket: 0 for bucket in keys}

    weight_sum = sum(positive.values())
    raw = {k: total * (v / weight_sum) for k, v in positive.items()}
    counts = {k: int(raw[k] // 1) for k in raw}
    assigned = sum(counts.values())
    remainder = total - assigned

    if remainder > 0:
        fractional_order = sorted(
            raw.keys(),
            key=lambda k: (raw[k] - counts[k], raw[k]),
            reverse=True,
        )
        for key in fractional_order:
            if remainder <= 0:
                break
            counts[key] = counts.get(key, 0) + 1
            remainder -= 1

    result = {bucket: 0 for bucket in keys}
    result.update(counts)
    return result


def _entry_has_highlights(entry: Mapping) -> bool:
    if not isinstance(entry, Mapping):
        return False
    highlights = entry.get("highlights") or entry.get("actions") or []
    if isinstance(highlights, str):
        return bool(highlights.strip())
    if isinstance(highlights, Sequence):
        return any(str(item).strip() for item in highlights)
    return False


def has_behavioral_grounding(dossier: Mapping | None) -> bool:
    """Behavioral bucket needs resume stories — not skills-only."""
    dossier = dossier or {}
    if dossier.get("resume_anchors"):
        return True
    if dossier.get("experience"):
        return True
    projects = dossier.get("projects") or []
    return any(_entry_has_highlights(item) for item in projects if isinstance(item, Mapping))


def has_concepts_grounding(dossier: Mapping | None) -> bool:
    """Concepts bucket needs JD substance."""
    dossier = dossier or {}
    return bool(
        dossier.get("must_have_skills")
        or dossier.get("overlap_skills")
        or dossier.get("jd_highlights")
    )


def has_situational_grounding(dossier: Mapping | None) -> bool:
    """Situational bucket needs gaps or bridges."""
    dossier = dossier or {}
    return bool(dossier.get("gap_skills") or dossier.get("transferable_bridges"))


def _skill_looks_code_like(skill: str) -> bool:
    normalized = str(skill or "").strip().lower()
    if not normalized:
        return False
    if normalized in _CODE_SKILL_HINTS:
        return True
    return any(hint in normalized for hint in _CODE_SKILL_HINTS)


def has_coding_grounding(dossier: Mapping | None, is_technical: bool) -> bool:
    """Coding bucket needs a technical role plus code-like skills."""
    if not is_technical:
        return False
    dossier = dossier or {}
    skills = list(dossier.get("overlap_skills") or []) + list(dossier.get("resume_skills") or [])
    return any(_skill_looks_code_like(skill) for skill in skills)


def compute_eligibility(
    dossier: Mapping | None,
    is_technical: bool,
    mix: Mapping[str, float] | None = None,
) -> dict[str, bool]:
    """Return per-bucket eligibility based on dossier grounding gates."""
    mix = mix or {}
    coding_requested = float(mix.get("coding", 0.0)) > 0.0
    return {
        "behavioral": has_behavioral_grounding(dossier),
        "concepts": has_concepts_grounding(dossier),
        "situational": has_situational_grounding(dossier),
        "coding": coding_requested and has_coding_grounding(dossier, is_technical),
    }


def _allocate_small_total(total: int, eligibility: Mapping[str, bool]) -> dict[str, int]:
    """When total is tiny, assign at most one question per eligible bucket by priority."""
    counts = {bucket: 0 for bucket in QUESTION_TYPES}
    remaining = max(0, int(total))
    for bucket in _BUCKET_PRIORITY_FOR_SMALL_TOTALS:
        if remaining <= 0:
            break
        if eligibility.get(bucket):
            counts[bucket] = 1
            remaining -= 1
    if remaining > 0 and any(eligibility.values()):
        eligible = [b for b in QUESTION_TYPES if eligibility.get(b)]
        idx = 0
        while remaining > 0 and eligible:
            bucket = eligible[idx % len(eligible)]
            counts[bucket] += 1
            remaining -= 1
            idx += 1
    return counts


def apply_grounding_redistribution(
    counts: Mapping[str, int],
    eligibility: Mapping[str, bool],
    original_weights: Mapping[str, float],
) -> tuple[dict[str, int], list[str]]:
    """Zero ineligible buckets and redistribute their counts among eligible ones."""
    notices: list[str] = []
    adjusted = {bucket: max(0, int(counts.get(bucket, 0))) for bucket in QUESTION_TYPES}
    blocked_total = sum(adjusted[b] for b in QUESTION_TYPES if not eligibility.get(b))
    for bucket in QUESTION_TYPES:
        if not eligibility.get(bucket) and adjusted[bucket] > 0:
            notices.append(
                f"{adjusted[bucket]} {bucket} question(s) skipped (insufficient dossier grounding)."
            )
            adjusted[bucket] = 0

    if blocked_total <= 0:
        return adjusted, notices

    eligible_weights = {
        bucket: max(0.0, float(original_weights.get(bucket, 0.0)))
        for bucket in QUESTION_TYPES
        if eligibility.get(bucket)
    }
    if not eligible_weights or sum(eligible_weights.values()) <= 0:
        notices.append(
            f"{blocked_total} question(s) could not be redistributed (no eligible buckets)."
        )
        return adjusted, notices

    redistribution = largest_remainder_allocate(blocked_total, eligible_weights)
    for bucket, extra in redistribution.items():
        if extra:
            adjusted[bucket] += extra
    notices.append(
        f"Redistributed {blocked_total} question(s) across "
        f"{', '.join(bucket for bucket in QUESTION_TYPES if redistribution.get(bucket))}."
    )
    return adjusted, notices


def apply_depth_profile(bucket_count: int, depth_profile: str = "balanced") -> dict[str, int]:
    """Split one bucket's count into beginner/medium/hard using a depth profile."""
    count = max(0, int(bucket_count))
    if count == 0:
        return {level: 0 for level in DIFFICULTY_LEVELS}

    profile_key = depth_profile if depth_profile in DEPTH_PROFILE_RATIOS else "balanced"
    ratios = DEPTH_PROFILE_RATIOS[profile_key]
    return largest_remainder_allocate(count, ratios, all_keys=DIFFICULTY_LEVELS)


def compute_type_difficulty(
    type_counts: Mapping[str, int],
    depth_profile: str = "balanced",
) -> dict[str, dict[str, int]]:
    """Apply depth profile within each type bucket."""
    return {
        bucket: apply_depth_profile(type_counts.get(bucket, 0), depth_profile)
        for bucket in QUESTION_TYPES
    }


def allocate_type_counts_by_difficulty_ratios(
    type_counts: Mapping[str, int],
    beginner_count: int,
    medium_count: int,
    hard_count: int,
) -> dict[str, dict[str, int]]:
    """
    Build a type × difficulty integer matrix that preserves both margins.

    Row totals  = type_counts (behavioral / concepts / situational / coding)
    Column totals = beginner_count / medium_count / hard_count

    Uses the independence table (row * col / N), floors each cell, then fills
    residuals by repeatedly placing one unit in the eligible cell farthest
    below its independence target. When row and column grand totals differ,
    difficulty columns are renormalized via LRM so the matrix stays feasible
    while type row totals remain exact.
    """
    rows = {bucket: max(0, int(type_counts.get(bucket, 0))) for bucket in QUESTION_TYPES}
    cols = {
        "beginner": max(0, int(beginner_count or 0)),
        "medium": max(0, int(medium_count or 0)),
        "hard": max(0, int(hard_count or 0)),
    }
    row_total = sum(rows.values())
    col_total = sum(cols.values())

    empty = {
        bucket: {level: 0 for level in DIFFICULTY_LEVELS} for bucket in QUESTION_TYPES
    }
    if row_total <= 0:
        return empty

    # Feasibility: column targets must sum to the type grand total.
    if col_total != row_total:
        if col_total <= 0:
            cols = largest_remainder_allocate(
                row_total,
                {"beginner": 1, "medium": 1, "hard": 1},
                all_keys=DIFFICULTY_LEVELS,
            )
        else:
            cols = largest_remainder_allocate(
                row_total, cols, all_keys=DIFFICULTY_LEVELS
            )

    result = {
        bucket: {level: 0 for level in DIFFICULTY_LEVELS} for bucket in QUESTION_TYPES
    }
    raw: dict[tuple[str, str], float] = {}
    for bucket in QUESTION_TYPES:
        for level in DIFFICULTY_LEVELS:
            if rows[bucket] == 0 or cols[level] == 0:
                raw[(bucket, level)] = 0.0
            else:
                raw[(bucket, level)] = rows[bucket] * cols[level] / row_total

    row_rem = dict(rows)
    col_rem = dict(cols)

    for bucket in QUESTION_TYPES:
        for level in DIFFICULTY_LEVELS:
            floored = int(raw[(bucket, level)] // 1)
            if floored <= 0:
                continue
            result[bucket][level] = floored
            row_rem[bucket] -= floored
            col_rem[level] -= floored

    def _best_cell() -> tuple[str, str] | None:
        best: tuple[str, str] | None = None
        best_score = None
        for bucket in QUESTION_TYPES:
            if row_rem[bucket] <= 0:
                continue
            for level in DIFFICULTY_LEVELS:
                if col_rem[level] <= 0:
                    continue
                # Prefer cells farthest below independence; break ties by raw then key order.
                score = (
                    raw[(bucket, level)] - result[bucket][level],
                    raw[(bucket, level)],
                    -QUESTION_TYPES.index(bucket),
                    -DIFFICULTY_LEVELS.index(level),
                )
                if best_score is None or score > best_score:
                    best_score = score
                    best = (bucket, level)
        return best

    remaining = sum(row_rem.values())
    while remaining > 0:
        cell = _best_cell()
        if cell is None:
            break
        bucket, level = cell
        result[bucket][level] += 1
        row_rem[bucket] -= 1
        col_rem[level] -= 1
        remaining -= 1

    return result


def compute_question_plan(
    total_count: int,
    dossier: Mapping | None,
    interview_focus: str | None = None,
    type_mix_override: Mapping[str, float] | None = None,
    depth_profile: str = "balanced",
    is_technical: bool | None = None,
    job_title: str = "",
    job_description: str = "",
) -> QuestionPlan:
    """Build a full question plan: focus, type counts, per-type difficulty, and notices."""
    total = max(0, int(total_count))
    if is_technical is None:
        is_technical = is_technical_role_heuristic(job_title, job_description)

    focus = normalize_focus_key(interview_focus) or infer_interview_focus(
        dossier,
        job_title=job_title,
        job_description=job_description,
        is_technical=is_technical,
    )

    if type_mix_override:
        mix = normalize_mix(type_mix_override, is_technical)
    else:
        mix = normalize_mix(get_preset_mix(focus), is_technical)

    eligibility = compute_eligibility(dossier, is_technical, mix)

    if total < 4:
        type_counts = _allocate_small_total(total, eligibility)
        notices: list[str] = []
    else:
        type_counts = largest_remainder_allocate(total, mix)
        type_counts, notices = apply_grounding_redistribution(type_counts, eligibility, mix)

    profile_key = depth_profile if depth_profile in DEPTH_PROFILE_RATIOS else "balanced"
    type_difficulty = compute_type_difficulty(type_counts, profile_key)

    return QuestionPlan(
        total_count=total,
        interview_focus=focus,
        depth_profile=profile_key,
        is_technical=bool(is_technical),
        type_counts=type_counts,
        type_difficulty=type_difficulty,
        eligibility=dict(eligibility),
        mix_percentages=dict(mix),
        notices=tuple(notices),
    )


def redistribute_generation_shortfall(
    type_counts: Mapping[str, int],
    bucket: str,
    shortfall: int,
    eligibility: Mapping[str, bool],
) -> tuple[dict[str, int], list[str]]:
    """Redistribute ungenerated questions after LLM refill exhaustion (Phase 2 helper)."""
    shortfall = max(0, int(shortfall))
    if shortfall <= 0 or bucket not in GENERATION_SHORTFALL_PRIORITY:
        return dict(type_counts), []

    adjusted = {b: max(0, int(type_counts.get(b, 0))) for b in QUESTION_TYPES}
    notices: list[str] = []
    remaining = shortfall

    for target in GENERATION_SHORTFALL_PRIORITY[bucket]:
        if remaining <= 0:
            break
        if not eligibility.get(target):
            continue
        adjusted[target] = adjusted.get(target, 0) + remaining
        notices.append(
            f"{remaining} {bucket} question(s) not generated; added to {target}."
        )
        remaining = 0

    if remaining > 0:
        notices.append(
            f"{remaining} {bucket} question(s) could not be recovered after generation shortfall."
        )

    return adjusted, notices
