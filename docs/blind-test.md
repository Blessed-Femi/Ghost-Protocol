# Blind test — CASE-002 Server room access review

> **All data in this document is fictional.** No real people, sites, systems or events are
> described. Nothing here is copied from a real incident report.
>
> **Written before the fixture and the tests.** The expected answers below were committed
> first, on purpose. CASE-002 is a *blind* case: the engine was built around CASE-001, so the
> values here were derived by hand from this document and the format of
> `backend/app/seed/case_001/`, **not** by running the engine. The history in this branch
> shows the order: expectations → fixture → tests.

## Why this exists

CASE-001 proves the engine works on the case it was designed for. That says little. The blind
test asks a harder question: does the same engine produce the same *kind* of answer on a case
it never saw? CASE-002 exercises the three behaviours the engine claims to have:

1. a clock that **runs slow**, so normalization must move the time **forward**;
2. a log row **copied between two sources** with a different timestamp;
3. an **approximate witness time**, which must stay **Unresolved**.

The engine is frozen for this task. No file under `backend/app/services/` or
`backend/app/models/` is touched. If the engine disagrees with an expectation below, the
test is left failing (marked `xfail` with the reason) and a separate issue is opened.

## Story

At a fictional data-centre, the server room was opened outside the approved maintenance
window. A security review collects five evidence items. Two of them disagree with the rest in
ways the system must surface **without accusing anyone**.

All times are site local time, **2026-10-12, UTC+01:00**. The incident window is
**02:00:00–03:00:00 local**. Internally the application stores UTC and keeps every original
source value unchanged.

## Evidence items (5)

| ID   | Item                          | Type  | Clock status                                        | What it contributes                                   |
| ---- | ----------------------------- | ----- | --------------------------------------------------- | ----------------------------------------------------- |
| E-01 | Server-room door access log   | CSV   | Reference (no offset)                               | Badge **B-217** opens the server-room door (row 6)    |
| E-02 | Security console export       | CSV   | Reference (no offset)                               | Contains a **copied** door row (row 1)                |
| E-03 | Corridor camera               | video | **Runs 90 s slow** → normalized = source **+ 90 s** | A person enters the server corridor                   |
| E-04 | Cabinet-door alarm audio      | audio | Reference (no offset)                               | A cabinet-door alarm sounds                           |
| E-05 | Duty technician statement     | PDF   | Approximate times only                              | The technician heard the alarm "around 02:30"         |

E-01 is authoritative for `DOOR_OPEN` / `DOOR_CLOSE`; E-02 is not. That is what makes E-01
row 6 the original and E-02 row 1 the copy.

As in CASE-001, video, audio and PDF extraction is simulated from seeded metadata and must be
labelled as such. CSV items are parsed deterministically.

## Expected events (answers, written by hand)

Sorted by normalized time. Every CSV row inside the incident window becomes an event; rows
outside the window are dropped. Local source times are shown next to the normalized UTC
values.

| Event  | Source locator        | Source time (local) | Normalized time (UTC) | Rule applied               | Expected state |
| ------ | --------------------- | ------------------- | --------------------- | -------------------------- | -------------- |
| EV-001 | E-01 · row 3          | 02:04:20            | 2026-10-12T01:04:20Z  | reference_clock            | Supported      |
| EV-002 | E-01 · row 4          | 02:06:05            | 2026-10-12T01:06:05Z  | reference_clock            | Supported      |
| EV-009 | E-02 · row 1          | 02:07:15            | 2026-10-12T01:07:15Z  | reference_clock            | **Contradicted** |
| EV-003 | E-01 · row 5          | 02:11:48            | 2026-10-12T01:11:48Z  | reference_clock            | Supported      |
| EV-012 | E-03 · timecode 00:31 | **02:14:30**        | **2026-10-12T01:16:00Z** | offset **+90 s** (source slow) | Supported |
| EV-004 | E-01 · row 6          | 02:22:00            | 2026-10-12T01:22:00Z  | reference_clock            | Supported      |
| EV-013 | E-04 · timecode 00:00:48 | 02:23:10         | 2026-10-12T01:23:10Z  | reference_clock            | Inferred       |
| EV-005 | E-01 · row 7          | 02:24:31            | 2026-10-12T01:24:31Z  | reference_clock            | Supported      |
| EV-014 | E-05 · page 1, para 4 | ~02:30             | 2026-10-12T01:30:00Z ±180 s | approximate ±180 s   | **Unresolved** |
| EV-006 | E-01 · row 8          | 02:38:14            | 2026-10-12T01:38:14Z  | reference_clock            | Supported      |
| EV-010 | E-02 · row 2          | 02:40:22            | 2026-10-12T01:40:22Z  | reference_clock            | Supported      |
| EV-007 | E-01 · row 9          | 02:51:09            | 2026-10-12T01:51:09Z  | reference_clock            | Supported      |
| EV-008 | E-01 · row 10         | 02:53:40            | 2026-10-12T01:53:40Z  | reference_clock            | Supported      |
| EV-011 | E-02 · row 3          | 02:58:41            | 2026-10-12T01:58:41Z  | reference_clock            | Supported      |

Rows outside the window are intentionally present in the CSVs (E-01 rows 1, 2 and 11) and must
**not** become events.

## Expected conflicts (answers, written by hand)

| ID   | Rule          | Type                 | Severity | Evidence           | Expected explanation (essence) |
| ---- | ------------- | -------------------- | -------- | ------------------ | ------------------------------ |
| C-01 | RULE-DUP-001  | Copied log record    | High     | E-01 r6, E-02 r1   | E-02 row 1 matches E-01 row 6 on badge, door and event code but is stamped **02:07:15** instead of **02:22:00**. Possible copy or import error. **Not proof of tampering.** |
| C-02 | RULE-TIME-001 | Clock offset         | Medium   | E-03               | E-03 clock runs **90 s slow**. Source 02:14:30 is normalized by **+90 s**. Original times preserved. |
| C-03 | RULE-CLAIM-001| Identity not established | Review | — (claim CL-04) | No source links the person in E-03 to badge B-217. |

### The three acceptance behaviours, stated exactly

1. **Offset direction and size.** E-03 is the only offset source. Its clock is **90 s slow**,
   so `offset_seconds == -90` and the normalized time is the source time **plus 90 s**:
   `2026-10-12T02:14:30+01:00` → `2026-10-12T01:16:00Z`. The rule text names a slow clock;
   the conflict explanation says "90 s slow" and normalizes "by +90 s".
2. **Duplicate pair.** The copied row is **E-01 row 6 → E-02 row 1**, on the key fields
   `badge_id = B-217`, `door = SERVER-ROOM`, `event_code = DOOR_OPEN`. The detector must link
   the pair `["E-01", "E-02"]` and mark the **copy** (E-02 row 1, EV-009) Contradicted, leaving
   the original (E-01 row 6, EV-004) Supported. Because the copy is stamped before the first
   person enters, the explanation also names that first entry (E-03, source 02:14:30).
3. **Approximate witness time.** E-05 produces EV-014 with `approximate == True`,
   `uncertainty_seconds == 180` and state **Unresolved**. It is never presented as exact.

## Expected claims (answers, written by hand)

| ID    | Statement                                             | State        | Supporting        |
| ----- | ----------------------------------------------------- | ------------ | ----------------- |
| CL-01 | The server-room door opened at 02:22:00               | Supported    | E-01 r6           |
| CL-02 | A person entered the server corridor at 02:16:00      | Supported    | E-03 (normalized) |
| CL-03 | The 02:23 alarm came from the server-room cabinet     | Inferred     | E-04, E-01        |
| CL-04 | The person in E-03 is the holder of badge B-217       | Unresolved   | —                 |
| CL-05 | A server-room door opening happened at 02:07:15       | Contradicted | E-02 r1           |
| CL-06 | The cabinet was accessed during the alarm             | Unresolved   | —                 |

CL-04 is an identity claim with no supporting link, so it must raise C-03
(`RULE-CLAIM-001`). No claim or event names a responsible person.

## Acceptance checks used by `backend/tests/test_blind_case.py`

- [ ] Exactly five evidence items: E-01 … E-05.
- [ ] E-03 is the only clock offset; `offset_seconds == -90` and it is described as **slow**.
- [ ] EV-012 keeps source `2026-10-12T02:14:30+01:00` and normalizes to
      `2026-10-12T01:16:00Z` (source **+ 90 s**).
- [ ] C-02 is `RULE-TIME-001`, names E-03, and says "90 s slow".
- [ ] C-01 is `RULE-DUP-001`, links `["E-01", "E-02"]` and events `["EV-004", "EV-009"]`,
      and its explanation says "not proof of tampering".
- [ ] EV-009 (the copy) is Contradicted; EV-004 (the original) stays Supported.
- [ ] EV-014 is Unresolved, approximate, with ±180 s uncertainty.
- [ ] Two runs of the engine give identical output.
