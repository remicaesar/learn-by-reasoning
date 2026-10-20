---
name: study
description: Run a study session on your book — a short warm-up quiz when one is due, then the next concept, taught problem-first with a teach-back.
disable-model-invocation: true
---

# Study session

`lbr` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lbr.py"`. Never edit the
`[ ]`/`[>]`/`[!]`/`[x]` markers or `read:` lines in `plan.md` by hand; change them
only with `lbr set` and `lbr read`, so the progress map stays true.

Read [teaching.md](teaching.md) before teaching anything. It is how every concept
is taught, and its rules hold for the whole session.

## 1. Find the book and where it stands

- If `plan.md` in the current directory starts with the line
  `<!-- learn-by-reasoning v1 -->` (check with `head -n 1 plan.md`), the book is the
  current directory. Otherwise run `lbr books` (one book per line: folder, title,
  concepts done, tab-separated). No books: say `/learn-by-reasoning:start
  <path-to-pdf>` makes one, and stop. One book: use it. Several: ask which with
  AskUserQuestion (header `Book`), or in plain text if it is not available.
- Run `lbr status "<book>"`. It prints:

  ```text
  next: <id> <title>     the concept to teach, or "-" when the book is finished
  quiz: <n>              how many warm-up questions are due
  shaky: <id,id>         concepts whose teach-back or quiz did not hold up ("-" if none)
  done: <id,id>          finished concepts ("-" if none)
  read: <chapter> <yes|no|unasked>   for the next concept's chapter
  ```

- Read `plan.md` (for the PDF path in `source:`, chapter titles and pages) and
  `journal.md` (preferences, the learner's earlier explanations, and the mistakes
  behind shaky concepts).
- If `lbr` prints an error, show that line, say `plan.md` needs it fixed, and stop.

## 2. Warm-up quiz, when `quiz` is above 0

Tell the learner in one line: "Warm-up first: <n> quick questions on earlier
concepts." Then ask the questions one at a time, waiting for each answer:

- Shaky ids first (use `journal.md` to aim at the mistake behind each), then a
  sample of done ones, preferring those not quizzed recently.
- Each question is a fresh case to reason about, not a request for a definition.
  Short: a few lines at most.
- After each answer, one or two lines of feedback: what was right, and what was
  missing if anything. No re-teaching here.
- A wrong answer: `lbr set "<book>" <id> shaky`, and add a one-line note under that
  concept in `journal.md` saying what went wrong.
- A right answer on a shaky id: `lbr set "<book>" <id> done`.

If `next` is `-`, the book is finished: after the quiz (if any), say so, run
`lbr progress "<book>"`, show it in a `text` code block, and stop.

## 3. Ask about the reading, once per chapter

If the `read:` line says `unasked`, ask once whether they have read chapter
<chapter> (show its title and pages) with AskUserQuestion (header `Reading`,
options **Yes, I've read it** and **Not yet**), or in plain text if it is not
available. Record it: `lbr read "<book>" <chapter> yes` or `... no`. Never ask again
for that chapter.

## 4. Teach the concept

1. `lbr set "<book>" <id> current`.
2. Read the concept's part of the book. Extract the chapter's pages to a temp file
   and find the concept in it with Grep and Read:

   ```sh
   tmp="$(mktemp -d)"; pdftotext -f <first> -l <last> -layout "<source>" "$tmp/chapter.txt"
   ```

   Teach from what the book says; its examples and exercises are your first source
   of problems.
3. Teach it exactly as `teaching.md` says: problem first and wait, then the
   explanation, then the teach-back.

## 5. Record the outcome

- Teach-back holds up (core idea stated correctly *and* applied to the fresh case):
  `lbr set "<book>" <id> done`.
- It did not hold up after your probing, or the learner wants to move on:
  `lbr set "<book>" <id> shaky`, and write the gap in `journal.md`. It will be
  quizzed first next time.
- Either way, append the learner's own explanation to `journal.md` under the concept.

`journal.md` layout (create sections as needed; dates from `date +%F`):

```markdown
## Preferences
explanation: story

## 1.1 <concept title>
- 2026-10-21 explained: "<the learner's own words, lightly trimmed>"
- 2026-10-21 shaky: <what was missing or wrong>
- 2026-10-24 quiz: wrong — <what went wrong>
```

If the session ends before the teach-back, leave the concept as it is: it stays in
progress and the next session resumes at it.

## 6. Next or stop

Ask whether to go on to the next concept or stop for now. To go on, run
`lbr status "<book>"` again and continue from step 3 (no second quiz in the same
session). To stop, run `lbr progress "<book>"` and show its output verbatim in a
`text` code block.
