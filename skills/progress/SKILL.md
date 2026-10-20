---
name: progress
description: Print the progress map of the book you are learning — chapters, concepts, shaky spots, where you are, and what the next session starts with.
disable-model-invocation: true
---

# Show progress

`lbr` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lbr.py"`.

1. Find the book.
   - If `plan.md` in the current directory starts with the line
     `<!-- learn-by-reasoning v1 -->` (check with `head -n 1 plan.md`), the book is
     the current directory.
   - Otherwise run `lbr books`. It prints one book per line: folder, title, and
     concepts done, separated by tabs. If it prints no books, say there is no book
     yet and that `/learn-by-reasoning:start <path-to-pdf>` makes one, then stop.
     If there is one book, use it. If there are several, ask which with
     AskUserQuestion (header `Book`, one option per title), or in plain text if
     AskUserQuestion is not available.
2. Run `lbr progress "<book folder>"`.
3. Show its output verbatim in a `text` code block, and add nothing else: no
   summary, no advice. If it printed an error instead, show the error line and say
   that `plan.md` needs that line fixed.
