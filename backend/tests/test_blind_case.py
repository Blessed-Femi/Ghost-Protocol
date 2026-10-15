"""Blind-test known-answer tests for CASE-002.

The expected values come from ``docs/blind-test.md``, which was committed *before* the fixture
and these tests. CASE-002 was not used to build the engine, so this file checks that the same
engine produces the answers we wrote down by hand:

* E-03 is the only clock offset and it is slow, so normalized = source + 90 s;
* E-02 row 1 copies E-01 row 6 with a different timestamp;
* E-05 carries an approximate witness time that must stay Unresolved.

No engine code is changed for this case.
"""

from app.models.domain import ClaimState, ConflictType, Severity
from app.services.store import CaseData


def case():
    return CaseData("case_002")


def by_id(items):
    return {i.id: i for i in items}


def test_five_fictional_evidence_items():
    data = case()
    assert data.case.id == "CASE-002"
    assert data.case.fictional is True
    assert [e.id for e in data.evidence] == ["E-01", "E-02", "E-03", "E-04", "E-05"]


def test_logs_are_hashed_and_metadata_evidence_is_simulated():
    data = case()
    hashed = {e.id for e in data.evidence if e.sha256}
    assert hashed == {"E-01", "E-02"}
    assert all(e.simulated for e in data.evidence if e.id not in hashed)


def test_only_the_corridor_camera_has_a_clock_offset():
    offsets = {e.id: e.clock.offset_seconds for e in case().evidence}
    assert offsets == {"E-01": 0, "E-02": 0, "E-03": -90, "E-04": 0, "E-05": 0}


def test_slow_clock_offset_moves_time_forward_by_90_seconds():
    ev = by_id(case().events)["EV-012"]
    assert ev.evidence_id == "E-03"
    # A slow clock is stored as a negative offset so that normalized = source - (-90).
    assert ev.offset_seconds == -90
    # The original source time is never overwritten.
    assert ev.source_time == "2026-10-12T02:14:30+01:00"
    # 02:14:30 + 01:00 + 90 s = 01:16:00Z.
    assert ev.normalized_time == "2026-10-12T01:16:00Z"
    assert "90s slow" in ev.normalization_rule


def test_clock_offset_conflict_reports_direction_and_size():
    c02 = by_id(case().conflicts)["C-02"]
    assert c02.rule_id == "RULE-TIME-001"
    assert c02.type is ConflictType.CLOCK_OFFSET
    assert c02.severity is Severity.MEDIUM
    assert c02.evidence_ids == ["E-03"]
    assert "90 s slow" in c02.explanation
    assert "normalized by +90 s" in c02.explanation
    assert "declared in the fixture" in c02.uncertain


def test_copied_row_links_the_original_and_the_copy():
    c01 = by_id(case().conflicts)["C-01"]
    assert c01.rule_id == "RULE-DUP-001"
    assert c01.type is ConflictType.COPIED_RECORD
    assert c01.severity is Severity.HIGH
    assert c01.evidence_ids == ["E-01", "E-02"]
    assert c01.event_ids == ["EV-004", "EV-009"]
    assert "matches E-01 row 6" in c01.explanation
    assert "02:07:15" in c01.explanation
    assert "02:22:00" in c01.explanation
    assert "before the first person enters" in c01.explanation
    assert "not proof of tampering" in c01.explanation


def test_copy_is_contradicted_and_original_stays_supported():
    events = by_id(case().events)
    assert events["EV-009"].state is ClaimState.CONTRADICTED
    assert events["EV-004"].state is ClaimState.SUPPORTED


def test_approximate_witness_time_is_unresolved():
    ev = by_id(case().events)["EV-014"]
    assert ev.evidence_id == "E-05"
    assert ev.approximate is True
    assert ev.uncertainty_seconds == 180
    assert ev.state is ClaimState.UNRESOLVED
    assert "approximate" in ev.normalization_rule


def test_expected_timeline_matches_the_written_answers():
    data = case()
    assert [e.id for e in data.events] == [
        "EV-001",
        "EV-002",
        "EV-009",
        "EV-003",
        "EV-012",
        "EV-004",
        "EV-013",
        "EV-005",
        "EV-014",
        "EV-006",
        "EV-010",
        "EV-007",
        "EV-008",
        "EV-011",
    ]
    assert [e.normalized_time for e in data.events] == [
        "2026-10-12T01:04:20Z",
        "2026-10-12T01:06:05Z",
        "2026-10-12T01:07:15Z",
        "2026-10-12T01:11:48Z",
        "2026-10-12T01:16:00Z",
        "2026-10-12T01:22:00Z",
        "2026-10-12T01:23:10Z",
        "2026-10-12T01:24:31Z",
        "2026-10-12T01:30:00Z",
        "2026-10-12T01:38:14Z",
        "2026-10-12T01:40:22Z",
        "2026-10-12T01:51:09Z",
        "2026-10-12T01:53:40Z",
        "2026-10-12T01:58:41Z",
    ]


def test_rows_outside_the_incident_window_do_not_become_events():
    # E-01 rows 1, 2 and 11 sit outside 02:00-03:00 and must be dropped.
    assert len([e for e in case().events if e.evidence_id == "E-01"]) == 8
    assert len([e for e in case().events if e.evidence_id == "E-02"]) == 3


def test_conflicts_are_in_rule_order():
    data = case()
    assert [c.id for c in data.conflicts] == ["C-01", "C-02", "C-03"]
    assert [c.rule_id for c in data.conflicts] == [
        "RULE-DUP-001",
        "RULE-TIME-001",
        "RULE-CLAIM-001",
    ]


def test_identity_claim_raises_a_review_conflict():
    c03 = by_id(case().conflicts)["C-03"]
    assert c03.rule_id == "RULE-CLAIM-001"
    assert c03.severity is Severity.REVIEW
    assert "CL-04" in c03.explanation


def test_expected_claim_states():
    states = {c.id: c.state for c in case().claims}
    assert states == {
        "CL-01": ClaimState.SUPPORTED,
        "CL-02": ClaimState.SUPPORTED,
        "CL-03": ClaimState.INFERRED,
        "CL-04": ClaimState.UNRESOLVED,
        "CL-05": ClaimState.CONTRADICTED,
        "CL-06": ClaimState.UNRESOLVED,
    }


def test_no_event_or_conflict_names_a_person_as_responsible():
    data = case()
    banned = ("suspect", "thief", "guilty", "responsible")
    for e in data.events:
        assert not any(word in e.description.lower() for word in banned)
    for c in data.conflicts:
        assert not any(word in c.explanation.lower() for word in banned)


def test_non_unresolved_claims_cite_evidence():
    for claim in case().claims:
        if claim.state is not ClaimState.UNRESOLVED:
            assert claim.links, claim.id


def test_hypotheses_point_at_an_existing_conflict():
    data = case()
    conflict_ids = {c.id for c in data.conflicts}
    for h in data.hypotheses:
        assert h.conflict_id in conflict_ids, h.id


def test_analysis_is_deterministic():
    a, b = case(), case()
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]
    assert [c.model_dump() for c in a.conflicts] == [c.model_dump() for c in b.conflicts]
    assert [c.model_dump() for c in a.claims] == [c.model_dump() for c in b.claims]
