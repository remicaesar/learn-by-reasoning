# Learn by Reasoning: design

Date: 2026-10-21
Status: reviewed, awaiting the learner's approval

## Intent

A Claude Code plugin that turns a book or a set of lecture notes into a chapter-by-chapter
course and teaches it by making the learner reason, not by explaining at them.

The first real use is Omer Tamuz's *Undergraduate Game Theory Lecture Notes*
(`~/Readings/ug game theory lectures.pdf`, 95 pages, 10 chapters).
The learner reads economics and finance material and found that it does not stick when they only read.
What they want, in their words: concepts "explained simply" and learning that is "actually forcing me to reason and think to teach."

Prior art is VibeWise (installed at `~/.claude/plugins/cache/anthropic-plugin-directory/vibe-wise/`), which does
this for coding: it asks for the learner's approach first and keeps learning notes in the project.
They like VibeWise and keep it for coding. This plugin is its counterpart for reading-heavy subjects, with no code anywhere in the learning.

## Goals

1. **Feed in material, get a plan.** Point the plugin at a PDF (book, lecture notes, similar).
   It reads the material and builds a learning plan: chapters in the book's order, and inside each chapter the concepts to learn.
   The learner sees the plan before starting and can skip or merge parts.
2. **Teach each concept problem-first.** Decided by the learner:
   1. A problem that needs the concept, which they reason through *before* any explanation.
   2. Then the explanation, either formal or as a story.
   3. Then they teach the concept back in their own words, as if to someone else.
      Claude probes the gaps in their explanation rather than correcting them outright.
      The concept is done only when their explanation holds up.
3. **Explain simply.** Plain language, short turns, one idea at a time.
4. **Warm-up quiz on return.** When a session starts and earlier concepts exist, a small quiz on them comes first, then the session carries on where they stopped.
5. **Clear progress, in the terminal.** A command prints a compact map of the book (the learner chose option A from three mockups):

   ```text
   Undergraduate Game Theory (Tamuz)      █████░░░░░░░░░░░░░░░ 2 of 10 chapters

    ✓ Ch 1  What is a Game?                4/4 concepts
    ▶ Ch 2  Extensive form games           5/9 concepts
         ✓ strategy = complete plan
         ✓ Nash equilibrium
         ✓ subgame perfect equilibrium
         ! empty threats        shaky: re-quiz next time
         ▶ backward induction   ← you are here
         · one deviation principle
    · Ch 3  Strategic form games
      …

    Next session: 3-question warm-up quiz, then backward induction
   ```

   It shows: an overall bar, each chapter's state and concept count, the concepts of the current chapter,
   shaky concepts, where they are, and what the next session starts with.
6. **Resume exactly.** Close a session, come back days later, and it picks up at the same concept.

## Non-goals

- No coding exercises or Python. This is for reasoning about the material, not programming it.
- No browser dashboard or web page for progress (option C was offered and not chosen).
- Not limited to economics. Nothing in the design should assume a subject; economics is the first use.
- Not a flashcard or spaced-repetition app. The warm-up quiz is the only review mechanism.
- No accounts, sharing, or multiple learners.
- Not published to a marketplace for now; it is installed locally.

## Anti-goals (failure even if it technically works)

- **Progress that is not clear.** The learner said this is what would make them quit after a week.
  If the progress map is ever confusing, stale, or wrong about where they are, the plugin has failed.
- Explaining before they have tried the problem.
- Long lectures, or jargon where plain words would do.
- Marking a concept done because they said "got it" rather than because their explanation held up.

## Decided by the learner

- Claude Code plugin, installed once, usable in any folder (like VibeWise).
- Input: PDFs such as books and lecture notes.
- Concept order within a session: problem, then explanation (formal or story), then teach-back.
- Short quiz on earlier concepts when returning, then continue.
- Progress shown in the terminal on request.
- **Reading is the learner's choice per chapter.** At the start of each chapter the plugin asks whether they have read it.
  If they have, sessions check and deepen what they took from it, and problems may build on the reading.
  If not, the session is how they meet each concept, and the book is the source the plugin teaches from; it may suggest pages to skim afterwards.
  The answer is recorded per chapter.
- Start fresh on the game theory notes. An earlier hand-made folder, `~/learning/game-theory`, is not reused and the plugin must not depend on it.

## Calls made by Claude (open to the learner's correction)

- **Name:** `learn-by-reasoning`. Project lives at `~/code/learn-by-reasoning`.
- **Commands** (as plugin skills):
  - `/learn-by-reasoning:start <path-to-pdf>`: read the material, build and show the plan, create the book's folder.
  - `/learn-by-reasoning:study`: run a session (quiz if due, then the next concept).
  - `/learn-by-reasoning:progress`: print the map.
- **One folder per book**, default `~/learning/<book-slug>/`, holding the plan and progress as plain Markdown files.
  The learner never needs to open them, but they are readable and survive uninstalling the plugin.
  The folder stores the path to the source PDF; it does not copy the PDF.
- **Concept states:** not started, in progress, shaky, done. "Shaky" means the teach-back did not hold up or a quiz answer was wrong; shaky concepts are quizzed first.
- **Quiz size:** about three questions, shaky concepts first, then a sample of done ones.
- **The progress map is drawn by a small script** that reads the progress file, so it looks identical every time and cannot drift from the saved state.
  Python 3 is acceptable here (it is the plugin's machinery, not the learning), as VibeWise does the same.
- **Which book a command acts on:** run inside a book's folder, it acts on that book; run anywhere else, it lists the books under `~/learning/` and asks.
- **Where problems come from:** the book's own examples and exercises first, reworded where needed; invented ones only when the book has none for that concept.
- **When a teach-back holds up:** the explanation states the core idea correctly *and* the learner applies it to a fresh case Claude gives. Fluent restatement alone is not enough.
- **Scanned PDFs** with no text layer are out of scope for the first version.
- **The record keeps the learner's own explanations** and the mistakes behind any shaky concept, so later sessions can target them.

## Constraints

- Claude Code reads PDFs at most 20 pages per request; `pdftotext` is installed at `/opt/homebrew/bin/pdftotext`.
  Planning a whole book must work within that.
- Must work across sessions with no memory beyond the book folder.
- Plain files only; no database, no network service.

## Left to the builder

- How the plan is extracted from the PDF (contents page, headings, or reading in chunks) and how concepts within a chapter are chosen.
- The exact Markdown layout of the plan and progress files, as long as the progress map can be drawn from them.
- Prompt wording inside the skills, provided the teaching order and anti-goals above hold.
- How to show the plan for confirmation and apply "skip" or "merge."

## How we will know it works

Run it end to end on the Tamuz notes:

1. `start` produces a plan whose chapters match the notes' 10 chapters and whose Chapter 2 concepts include subgame perfect equilibrium and backward induction.
2. A `study` session on Chapter 1 opens with a problem, gives no explanation before the learner answers, and does not mark a concept done on a weak teach-back.
3. After quitting and starting a new session, a warm-up quiz runs first and the session resumes at the right concept.
4. `progress` prints the map above with correct counts and the right current concept.
