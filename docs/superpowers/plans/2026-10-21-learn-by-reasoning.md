# Learn by Reasoning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Claude Code plugin that turns a PDF into a chapter-by-chapter concept plan, teaches each concept problem-first with a teach-back, and shows progress as a terminal map.

**Architecture:** Three prompt-only skills (`start`, `study`, `progress`) carry the teaching. One stdlib-only Python script, `scripts/lbr.py`, owns everything that must be exact: parsing and rewriting the book's `plan.md`, drawing the progress map, and finding books. The skills never hand-edit state markers; they call the script, so the map cannot drift from the saved state.

**Tech Stack:** Claude Code plugin (`.claude-plugin/plugin.json`, `marketplace.json`, `skills/*/SKILL.md`), Python 3 standard library only, `unittest` for tests, `pdftotext` for reading PDFs.

**Spec:** `docs/superpowers/specs/2026-10-21-learn-by-reasoning-design.md`

## Global Constraints

- Plugin name `learn-by-reasoning`; commands `/learn-by-reasoning:start <path-to-pdf>`, `/learn-by-reasoning:study`, `/learn-by-reasoning:progress`.
- One folder per book, default `~/learning/<book-slug>/`; plain Markdown only; the PDF is referenced by path, never copied.
- Concept states: not started, in progress, shaky, done.
- Quiz: about three questions, shaky first, then a sample of done ones.
- Teaching order per concept: problem first, then explanation (formal or story), then teach-back. No explanation before the learner has tried.
- Done only when the explanation states the core idea correctly and the learner applies it to a fresh case.
- Per chapter, ask once whether the learner has read it; record the answer.
- No coding exercises in the learning; no browser dashboard; nothing subject-specific; scanned PDFs out of scope.
- Python: standard library only (no pip installs); scripts invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lbr.py" ...`.
- Skills are user-invoked only: `disable-model-invocation: true` in each SKILL.md frontmatter (pattern from VibeWise).

## The plan.md format (shared by every task)

```markdown
<!-- learn-by-reasoning v1 -->
# Undergraduate Game Theory Lecture Notes
source: ~/Readings/ug game theory lectures.pdf
author: Omer Tamuz

## 1. What is a Game?
pages: 7
read: unasked
- [x] 1.1 The four parts of a game
- [ ] 1.2 Strategy as a rule

## 2. Finite extensive form games with perfect information
pages: 8-16
read: yes
- [x] 2.1 Strategy = complete contingency plan
- [!] 2.4 Empty threats
- [>] 2.5 Backward induction
- [ ] 2.6 One deviation principle
```

- Line 1 is the exact marker `<!-- learn-by-reasoning v1 -->`; a folder is a book folder iff `plan.md` starts with it.
- Markers: `[ ]` not started, `[>]` in progress, `[!]` shaky, `[x]` done. At most one `[>]` in the file; the script enforces it.
- Concept ids are `<chapter>.<n>`, unique in the file. `read:` is `yes`, `no`, or `unasked`.
- `journal.md` in the same folder is free text owned by the skills: per concept, the learner's own explanation and the mistakes behind any shaky mark. The script never reads it.

## Review Focus

1. A malformed or hand-edited `plan.md` (missing marker, duplicate id, unknown marker): every command prints one plain-English line naming the file and line, exit code 2, no traceback. Test in Task 1.
2. A finished book (no `[>]` and no `[ ]`): the map says `Book complete` instead of a next concept. Test in Task 1.
3. Long concept or chapter names: rows truncated with `…` so the map never wraps at 80 columns. Test in Task 1.
4. Non-ASCII titles (Turkish, accented): parse, slug and render without error; slug transliterates (`ı`→`i`, `ş`→`s`, `ğ`→`g`, `ç`→`c`, `ö`→`o`, `ü`→`u`). Test in Task 2.
5. `set` on an id that does not exist, or a second `in-progress`: refused with a clear message, file unchanged; setting a new `in-progress` demotes the old one to `[ ]` unless it is `[x]`/`[!]`. Test in Task 2.

---

### Task 1: Plugin skeleton, plan parser, and the progress map

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (same shape as VibeWise's; `source: "./"`)
- Create: `scripts/lbr.py`
- Create: `tests/test_lbr.py`, `tests/fixtures/tamuz_plan.md` (the example above, extended to all 10 chapter headings with at least one concept each)
- Create: `README.md` (install and the three commands, copied from "How to use" below)

**Interfaces:**
- Produces, in `scripts/lbr.py`:
  - `@dataclass Concept(id: str, title: str, state: str)` with `state` in `{"todo","current","shaky","done"}`
  - `@dataclass Chapter(number: str, title: str, pages: str, read: str, concepts: list[Concept])`
  - `@dataclass Book(title: str, source: str, author: str, chapters: list[Chapter])`
  - `class PlanError(Exception)` whose message is `"<path>:<line>: <reason>"`
  - `parse_plan(path: Path) -> Book`
  - `render_map(book: Book, width: int = 80) -> str`
  - CLI: `lbr.py progress <book-dir>` prints `render_map`; `PlanError` → message on stderr, exit 2.

- [ ] **Step 1: Write the failing tests** in `tests/test_lbr.py`:
  - `test_parse_fixture`: 10 chapters; chapter 2 has `read == "yes"` and concept `2.5` with `state == "current"`.
  - `test_map_header`: first line contains the book title and `0 of 10 chapters` (no chapter fully done in fixture) and `of <total> concepts`; bar is 20 cells of `█`/`░`, filled `round(20*done/total)`.
  - `test_map_expands_only_current_chapter`: concept rows appear for chapter 2 only; the `2.5` row ends with `← you are here`; the `2.4` row contains `shaky`.
  - `test_chapter_symbols`: `✓` for all-done chapter, `▶` for the chapter holding `[>]`, `!` for a non-current chapter containing `[!]`, `·` otherwise.
  - `test_next_session_line`: last line is `Next session: 3-question warm-up quiz, then Backward induction` when done+shaky ≥ 3; with done+shaky = 1 it says `1-question`; with 0 it omits the quiz clause.
  - `test_book_complete` (Review Focus 2), `test_truncates_long_names` (Review Focus 3: every line `len <= 80`), `test_malformed_plan` (Review Focus 1: missing marker, duplicate id, `[?]` marker each raise `PlanError` with the line number; CLI exits 2 with no `Traceback` in stderr).

- [ ] **Step 2: Run** `python3 -m unittest discover -s tests -v`. Expected: FAIL, `lbr` has no `parse_plan`.

- [ ] **Step 3: Implement** the dataclasses, `parse_plan`, `render_map`, and the `progress` subcommand (`argparse`). Next concept = the `[>]` concept, else the first `[ ]` in file order. Chapter "done" = every concept `[x]`.

- [ ] **Step 4: Run** the tests. Expected: all PASS. Then `python3 scripts/lbr.py progress tests/fixtures` (fixture dir must contain `plan.md`) and eyeball it against the spec's map.

- [ ] **Step 5: Red-proof** each new test: break the guarded line (e.g. drop the `← you are here` suffix, skip truncation), watch the named test fail, restore. Record each pair in the commit body.

- [ ] **Step 6: Commit** `feat: plugin skeleton, plan parser and progress map`.

### Task 2: State changes and finding books

**Files:**
- Modify: `scripts/lbr.py`
- Modify: `tests/test_lbr.py`

**Interfaces:**
- Consumes: `parse_plan`, `Book`, `PlanError` from Task 1.
- Produces:
  - `set_state(path: Path, concept_id: str, state: str) -> None` — rewrites only that concept's marker line, preserves every other byte; `state="current"` demotes any other `[>]` to `[ ]`.
  - `set_read(path: Path, chapter_number: str, value: str) -> None` — `value` in `{"yes","no"}`.
  - `slugify(title: str) -> str`
  - `find_books(root: Path) -> list[tuple[Path, Book]]` — immediate subfolders of `root` whose `plan.md` has the marker.
  - CLI: `lbr.py set <book-dir> <id> <todo|current|shaky|done>`, `lbr.py read <book-dir> <chapter> <yes|no>`, `lbr.py books [--root ~/learning]` (one line per book: folder, title, `N of M concepts done`), `lbr.py slug "<title>"`, `lbr.py status <book-dir>` (prints machine-readable lines: `next: <id> <title>`, `quiz: <n>`, `shaky: <id,id>`, `done: <id,id>`, `read: <chapter> <value>` for the next concept's chapter).

- [ ] **Step 1: Write the failing tests:** `test_set_state_rewrites_one_line` (diff of file is exactly one line), `test_set_current_demotes_previous`, `test_set_unknown_id_refused` and `test_set_keeps_file_on_error` (Review Focus 5), `test_set_read`, `test_slugify_turkish` (`"Oyun Kuramı: Giriş"` → `"oyun-kurami-giris"`, Review Focus 4), `test_find_books_ignores_unmarked` (temp dir with one marked and one unmarked `plan.md`), `test_status_lines` on the fixture (`next: 2.5 Backward induction`, `quiz: 3`).
- [ ] **Step 2: Run** tests. Expected: new tests FAIL.
- [ ] **Step 3: Implement.** Write via temp file + `os.replace` so a crash never leaves half a file.
- [ ] **Step 4: Run** tests. Expected: all PASS.
- [ ] **Step 5: Red-proof** each new test as in Task 1; record pairs.
- [ ] **Step 6: Commit** `feat: state changes, slugs and book discovery`.

### Task 3: The `start` skill

**Files:**
- Create: `skills/start/SKILL.md`

**Interfaces:**
- Consumes: `lbr.py slug`, `lbr.py progress`, the plan.md format.
- Produces: a book folder with `plan.md` (all concepts `[ ]`, every `read: unasked`) and an empty `journal.md`.

- [ ] **Step 1: Write SKILL.md** (`name: start`, `disable-model-invocation: true`, `argument-hint: <path-to-pdf>`). It instructs Claude to:
  1. Check the path exists and `pdftotext -layout` yields text; if the text is empty, say scanned PDFs aren't supported yet and stop.
  2. Extract to a temp file and read the contents pages and headings first; read chapters in chunks only as needed to choose concepts. 3–9 concepts per chapter, each a single idea the learner could be asked to explain, in book order, with page ranges.
  3. Propose folder `~/learning/<slug>/`; if it exists and holds a plan, stop and say so (never overwrite).
  4. Show the plan as a short numbered outline and ask for changes (skip, merge, rename) with AskUserQuestion; apply them; write `plan.md` exactly in the v1 format and an empty `journal.md`.
  5. Run `lbr.py progress <dir>` to prove the file parses, then tell the learner the next step: `cd` into the folder, run `claude`, then `/learn-by-reasoning:study`.
- [ ] **Step 2: Verify** by installing locally (see "How to use") and running `start` on the Tamuz notes: plan has 10 chapters; chapter 2 includes subgame perfect equilibrium and backward induction; `progress` prints without error. Save the session transcript excerpt to `docs/verification/start.md`.
- [ ] **Step 3: Commit** `feat: start skill`.

### Task 4: The `study` and `progress` skills

**Files:**
- Create: `skills/study/SKILL.md`, `skills/study/teaching.md`
- Create: `skills/progress/SKILL.md`

**Interfaces:**
- Consumes: `lbr.py books|status|set|read|progress`; `journal.md`.

- [ ] **Step 1: Write `progress/SKILL.md`:** resolve the book (cwd has a marked `plan.md`, else `lbr.py books` and ask which), run `lbr.py progress <dir>`, show the output verbatim in a code block, add nothing else.
- [ ] **Step 2: Write `study/SKILL.md`** with this session flow:
  1. Resolve the book as in progress. Run `lbr.py status`.
  2. If `quiz: n` > 0: ask n short questions, one at a time, shaky ids first then a sample of done ones, each a fresh case rather than a definition. A wrong answer → `lbr.py set <id> shaky` and a one-line note in `journal.md`; a right answer on a shaky id → `done`.
  3. If the next concept's chapter has `read: unasked`, ask once whether they've read it (pages shown) and record with `lbr.py read`.
  4. `lbr.py set <id> current`. Read that concept's pages from the PDF. Teach per `teaching.md`.
  5. On a teach-back that holds up → `set done`; otherwise → `set shaky`, journal the gap. Append the learner's own explanation to `journal.md` either way.
  6. Offer the next concept or a stop; on stop, run `lbr.py progress` and show it.
- [ ] **Step 3: Write `study/teaching.md`** with the rules, in this order: problem first, and wait — no hint, definition or explanation until the learner has answered; draw the problem from the book's own example or exercise for that concept, reworded, inventing one only if the book has none; if they read the chapter, the problem may build on it, otherwise it must stand alone; after their attempt, explain in plain words, formal or as a story (ask which they want the first time, then remember it in `journal.md` under `## Preferences`); then ask them to teach it back as if to a friend; probe gaps with questions rather than corrections; to pass, the explanation states the core idea *and* they apply it to a fresh case you give; never pass on "got it"; short turns, one idea at a time, no jargon without a plain-words gloss.
- [ ] **Step 4: Verify** with a role-played learner on the Tamuz notes and save excerpts to `docs/verification/study.md`, showing: (a) Chapter 1 session opens with a problem and gives no explanation before the answer; (b) a deliberately weak teach-back ends `shaky`, not `done`; (c) after ending and restarting, the warm-up quiz runs first and the session resumes at the right concept; (d) `progress` shows correct counts and the right current concept.
- [ ] **Step 5: Commit** `feat: study and progress skills`.

## How to use (goes into README.md)

```text
/plugin marketplace add ~/code/learn-by-reasoning
/plugin install learn-by-reasoning@learn-by-reasoning
# restart Claude Code
/learn-by-reasoning:start "<path to a PDF>"
cd ~/learning/<book-folder> && claude
/learn-by-reasoning:study
/learn-by-reasoning:progress
```
