# Learn by Reasoning

A Claude Code plugin that turns a book or a set of lecture notes (a PDF) into a
chapter-by-chapter course, and teaches it by making you reason rather than by
explaining at you. For each concept you get:

1. a problem that needs the concept, which you work through before any explanation;
2. the explanation, in plain words, either formal or as a story;
3. a teach-back: you explain it in your own words and apply it to a fresh case.
   A concept is done only when your explanation holds up.

When you come back after a break, a short warm-up quiz on earlier concepts comes
first, then the session carries on exactly where you stopped. Progress is a
compact map of the book, printed in the terminal.

It needs Claude Code, Python 3 (standard library only) and `pdftotext`
(`brew install poppler`). PDFs must have a text layer; scanned PDFs are not
supported yet.

## How to use

```text
/plugin marketplace add remicaesar/learn-by-reasoning
/plugin install learn-by-reasoning@learn-by-reasoning
# restart Claude Code
/learn-by-reasoning:start "<path to a PDF>"
cd ~/learning/<book-folder> && claude
/learn-by-reasoning:study
/learn-by-reasoning:progress
```

- `start <path-to-pdf>` reads the material, shows you the plan (chapters in the
  book's order, the concepts inside each) for changes, and creates the book's
  folder under `~/learning/`.
- `study` runs a session: the warm-up quiz if one is due, then the next concept.
- `progress` prints the map.

Run inside a book's folder, a command acts on that book; anywhere else, it lists
the books under `~/learning/` and asks which one.

## Updating

```text
/plugin marketplace update learn-by-reasoning
```

## What is in a book folder

`~/learning/<book-slug>/` holds two plain Markdown files. You never need to open
them, and they survive uninstalling the plugin.

- `plan.md` — the chapters, their pages, whether you read each chapter, and every
  concept with its state: `[ ]` not started, `[>]` in progress, `[!]` shaky,
  `[x]` done. It points at the source PDF; the PDF is never copied.
- `journal.md` — your own explanations, and the mistakes behind any shaky concept,
  so later sessions can target them.

`scripts/lbr.py` reads and updates `plan.md` and draws the map, so the map always
matches the saved state.

## Development

```text
python3 -m unittest discover -s tests -v
python3 scripts/lbr.py progress tests/fixtures
```

## License

MIT — see [LICENSE](LICENSE).
