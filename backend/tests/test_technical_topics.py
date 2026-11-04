"""Unit tests for technical_topics extraction/slicing in the interview dossier."""
from INTERVIEW.question_generation import (
    _coerce_technical_topics,
    _dossier_slice_for_type,
    _empty_dossier,
    _normalize_parsed_dossier,
)


def test_coerce_accepts_strings_and_dicts_and_dedupes():
    out = _coerce_technical_topics(
        [
            "LOD expressions",
            {"topic": "lod expressions", "source": "dup"},
            {"topic": "Extract tuning", "source": "Trane", "tech": "Tableau, BigQuery", "jd_tie": "performance"},
            {"topic": ""},
            42,
        ]
    )
    assert [t["topic"] for t in out] == ["LOD expressions", "Extract tuning"]
    assert out[1]["tech"] == ["Tableau", "BigQuery"]
    assert out[1]["jd_tie"] == "performance"


def test_coerce_respects_limit_and_non_list():
    assert _coerce_technical_topics(None) == []
    assert len(_coerce_technical_topics([f"t{i}" for i in range(20)], limit=8)) == 8


def test_normalized_dossier_carries_topics():
    d = _normalize_parsed_dossier({"technical_topics": ["Data reconciliation"]}, "BI Dev")
    assert d["technical_topics"][0]["topic"] == "Data reconciliation"
    assert _empty_dossier("BI Dev")["technical_topics"] == []


def test_legacy_dossier_without_topics_still_slices():
    legacy = {
        "job_title": "BI Dev",
        "projects": [{"name": "Apple RE", "tech": ["Tableau", "SQL"], "highlights": ["Built LOD KPIs"]}],
        "experience": [{"company": "Quest", "tech": ["Tableau"], "highlights": ["Migrated reports"]}],
    }
    concepts = _dossier_slice_for_type(legacy, "concepts")
    assert concepts["technical_topics"] == []
    names = [p["name"] for p in concepts["project_tech"]]
    assert names == ["Apple RE", "Quest"]
    for kind in ("behavioral", "situational"):
        assert _dossier_slice_for_type(legacy, kind)["technical_topics"] == []
