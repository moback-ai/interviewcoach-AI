"""Unit tests for dossier highlights coercion and anchor bundles."""
from INTERVIEW.question_generation import (
    HIGHLIGHTS_MAX,
    JD_HIGHLIGHTS_MAX,
    _coerce_experience_list,
    _coerce_highlights,
    _coerce_project_list,
    _dossier_anchor_bundles,
    _normalize_parsed_dossier,
)


def test_coerce_highlights_from_python_list_string():
    raw = "['Interacted with the BA.', 'Built Apex triggers.']"
    out = _coerce_highlights(raw, limit=HIGHLIGHTS_MAX)
    assert len(out) == 2
    assert out[0].startswith("Interacted")
    assert "['" not in out[0]
    assert out[1].startswith("Built")


def test_coerce_highlights_from_plain_string():
    out = _coerce_highlights("Owned change-set deployments end to end", limit=4)
    assert out == ["Owned change-set deployments end to end"]


def test_coerce_highlights_native_list_capped():
    items = [f"Bullet {i}" for i in range(10)]
    out = _coerce_highlights(items, limit=HIGHLIGHTS_MAX)
    assert len(out) == HIGHLIGHTS_MAX
    assert out[0] == "Bullet 0"


def test_coerce_experience_prefers_highlights_over_description_list():
    rows = _coerce_experience_list(
        [
            {
                "company": "Acme",
                "title": "Engineer",
                "description": ["Did A", "Did B", "Did C"],
            }
        ],
        limit=5,
    )
    assert len(rows) == 1
    assert "description" not in rows[0]
    assert rows[0]["highlights"] == ["Did A", "Did B", "Did C"]


def test_coerce_project_legacy_description_string():
    rows = _coerce_project_list(
        [{"name": "Retail", "description": "Implemented Salesforce CRM flows"}],
        limit=5,
    )
    assert rows[0]["highlights"] == ["Implemented Salesforce CRM flows"]
    assert "description" not in rows[0]


def test_normalize_jd_highlights_from_legacy_excerpt():
    dossier = _normalize_parsed_dossier(
        {
            "jd_excerpt": "Need AWS and Node.js\nBuild cloud apps",
            "must_have_skills": ["AWS"],
            "experience": [],
            "projects": [],
        },
        "AWS Engineer",
    )
    assert "jd_excerpt" not in dossier
    assert len(dossier["jd_highlights"]) >= 1
    assert dossier["schema_version"] == 2


def test_normalize_jd_highlights_native_capped():
    dossier = _normalize_parsed_dossier(
        {
            "jd_highlights": [f"Point {i}" for i in range(12)],
            "must_have_skills": ["AWS"],
        },
        "AWS Engineer",
    )
    assert len(dossier["jd_highlights"]) == JD_HIGHLIGHTS_MAX


def test_normalize_jd_highlights_fallback_to_responsibilities():
    dossier = _normalize_parsed_dossier(
        {
            "responsibilities": ["Design AWS apps", "Own CI/CD"],
            "must_have_skills": ["AWS"],
        },
        "AWS Engineer",
    )
    assert dossier["jd_highlights"] == ["Design AWS apps", "Own CI/CD"]


def test_anchor_bundles_use_first_highlights():
    dossier = {
        "companies": ["Acme"],
        "projects": [
            {
                "name": "Retail Project",
                "tech": ["Apex"],
                "highlights": [
                    "Built Salesforce triggers for order sync",
                    "Owned deployment cadence",
                ],
            }
        ],
        "experience": [
            {
                "company": "Acme",
                "title": "Developer",
                "tech": ["Salesforce"],
                "highlights": ["Led CRM integration work"],
            }
        ],
        "resume_anchors": [],
    }
    bundles = _dossier_anchor_bundles(dossier, limit=5)
    assert bundles
    retail = next(b for b in bundles if b["project"] == "Retail Project")
    assert "Built Salesforce triggers" in retail["artifact"]
    assert "['" not in retail["artifact"]
