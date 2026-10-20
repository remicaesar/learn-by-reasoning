---
name: start
description: Read a PDF (a book or lecture notes), build a chapter-by-chapter learning plan, show it for changes, and create the book's folder.
argument-hint: <path-to-pdf>
disable-model-invocation: true
---

# Start a book

The learner gave this material: `$ARGUMENTS`

Turn it into a plan of chapters and concepts, show it, apply their changes, and
create the book's folder. Do not teach anything here; teaching happens in
`/learn-by-reasoning:study`.

`lbr` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lbr.py"`.

## 1. Check the PDF

- If no path was given, ask for one and stop.
- Resolve the path (expand `~`, keep it absolute). If the file does not exist or is
  not a PDF, say so in one line and stop.
- Extract the text to a temp folder, never next to the PDF:

  ```sh
  tmp="$(mktemp -d)"; pdftotext -layout "<pdf>" "$tmp/book.txt"
  tr -d '[:space:]' < "$tmp/book.txt" | wc -c
  ```

  If `pdftotext` is missing, say to install it with `brew install poppler` and stop.
  If the count is near zero (under about 200 characters for the whole file), the PDF
  is scanned images with no text layer: say scanned PDFs are not supported yet and stop.

## 2. Build the plan

Work from `$tmp/book.txt` with Grep and Read (offset/limit), not by reading the PDF
whole. pdftotext separates pages with a form feed, so the page holding a phrase is:

```sh
awk -v RS='\f' 'index($0, "<phrase>") {print NR; exit}' "$tmp/book.txt"
```

Use these PDF page numbers (the ones `pdftotext -f N -l M` takes) everywhere.

1. Find the title, the author, and the contents page or the chapter headings.
   Chapters are the book's own top-level chapters, in the book's order, with the
   book's numbers. Front matter (preface, acknowledgments, contents) and back matter
   (references, index) are not chapters.
2. Give each chapter its page range, from its first page to the page before the next
   chapter starts.
3. Choose the concepts of each chapter: read the chapter in chunks only as far as you
   need to choose them. Each concept is one idea the learner could be asked to explain
   and apply, named in plain words in at most about 40 characters. 3 to 9 per chapter,
   in the order the book introduces them. Prefer the ideas the chapter builds on later
   over its examples; an example belongs inside a concept, not as its own concept,
   unless the book treats it as a central idea in its own right.

## 3. Choose the folder

Run `lbr slug "<title>"`. Propose `~/learning/<slug>/`. If the learner asked for a
different place, use that instead.

If the folder already holds a `plan.md`, stop: say a book already lives there and
that `/learn-by-reasoning:study` continues it. Never overwrite or delete anything in
an existing folder.

## 4. Show the plan and apply changes

Show the plan as a short numbered outline, one chapter per line with its pages and
its concepts indented beneath it, then the proposed folder. Keep it compact; no
commentary on each concept.

Then ask with AskUserQuestion (one question, header `Plan`): options **Looks good**
and **Change something**. If AskUserQuestion is not available, ask the same in
plain text and wait for the answer.

If they want changes, ask what to change in plain words, then apply them:

- **skip** a chapter or concept: remove it from the plan;
- **merge** concepts: one concept whose name covers both;
- **rename**: use their name;
- **add** or **split**: as asked.

Show the changed outline again and ask again, until they say it looks good.

## 5. Write the folder

Create the folder. Write `plan.md` with the Write tool in exactly this format:

```markdown
<!-- learn-by-reasoning v1 -->
# <title>
source: <absolute path to the PDF>
author: <author, or blank>

## <chapter number>. <chapter title>
pages: <first>-<last>
read: unasked
- [ ] <chapter number>.1 <concept>
- [ ] <chapter number>.2 <concept>

## <next chapter number>. <next chapter title>
...
```

- The first line is exactly `<!-- learn-by-reasoning v1 -->`.
- Chapters keep the book's numbers even when one was skipped. Concepts are numbered
  `<chapter>.1`, `<chapter>.2`, … in plan order after the learner's changes.
- Every concept starts as `[ ]` and every chapter as `read: unasked`.
- One blank line between chapters, nothing else in the file.
- The PDF stays where it is; the folder only points at it.

Create an empty `journal.md` next to it.

## 6. Prove it and hand over

Run `lbr progress "<folder>"`. If it prints an error, fix the line it names in
`plan.md` and run it again until it prints the map. Show the map in a code block.

Then tell the learner the next step, in one short paragraph:

```text
cd "<folder>" && claude
/learn-by-reasoning:study
```

Each study session starts with a problem to reason through, then the explanation,
then they teach it back.
