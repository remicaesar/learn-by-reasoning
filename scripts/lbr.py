#!/usr/bin/env python3
"""Plan, progress and book discovery for learn-by-reasoning.

Owns everything about a book folder that must be exact: parsing plan.md and
drawing the progress map. Skills call this script instead of editing state
markers by hand, so the map cannot drift from the saved state.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

MARKER = "<!-- learn-by-reasoning v1 -->"

STATE_BY_MARK = {" ": "todo", ">": "current", "!": "shaky", "x": "done"}
READ_VALUES = ("yes", "no", "unasked")

BAR_CELLS = 20
YOU_ARE_HERE = "← you are here"
UP_NEXT = "← up next"
SHAKY_NOTE = "shaky: re-quiz next time"
MAX_QUIZ = 3

CHAPTER_RE = re.compile(r"^## (\d+)\. (\S.*)$")
FIELD_RE = re.compile(r"^(pages|read): ?(.*)$")
HEADER_RE = re.compile(r"^(source|author): ?(.*)$")
CONCEPT_RE = re.compile(r"^- \[(.)\] (\d+\.\d+) (\S.*)$")


class PlanError(Exception):
    """A plan.md that cannot be used; the message names the file and line."""

    def __init__(self, path, line, reason):
        where = f"{path}:{line}" if line else f"{path}"
        super().__init__(f"{where}: {reason}")


@dataclass
class Concept:
    id: str
    title: str
    state: str
    line: int = field(default=0, compare=False, repr=False)


@dataclass
class Chapter:
    number: str
    title: str
    pages: str
    read: str
    concepts: list = field(default_factory=list)
    line: int = field(default=0, compare=False, repr=False)
    read_line: int = field(default=0, compare=False, repr=False)


@dataclass
class Book:
    title: str
    source: str
    author: str
    chapters: list = field(default_factory=list)


def read_lines(path):
    """The file's lines with their line endings, or PlanError."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read().splitlines(keepends=True)
    except FileNotFoundError:
        raise PlanError(path, 0, "no plan.md here (not a book folder)") from None
    except UnicodeDecodeError:
        raise PlanError(path, 0, "not UTF-8 text") from None
    except OSError as e:
        raise PlanError(path, 0, f"cannot read ({e.strerror})") from None


def parse_plan(path):
    path = Path(path)
    lines = [line.rstrip("\r\n") for line in read_lines(path)]
    if not lines or lines[0].rstrip() != MARKER:
        raise PlanError(path, 1, f"first line must be the marker {MARKER}")

    book = Book(title="", source="", author="")
    seen_ids = {}
    seen_chapters = set()
    current_at = None
    chapter = None

    def finish(ch):
        if ch is None:
            return
        for name, value in (("pages", ch.pages), ("read", ch.read)):
            if value is None:
                raise PlanError(path, ch.line, f"chapter {ch.number} has no '{name}:' line")
        if not ch.concepts:
            raise PlanError(path, ch.line, f"chapter {ch.number} has no concepts")

    for n, text in enumerate(lines[1:], start=2):
        stripped = text.strip()
        if not stripped:
            continue
        if chapter is None and not book.title:
            if text.startswith("# "):
                book.title = text[2:].strip()
                continue
            raise PlanError(path, n, "expected the book title as '# Title'")
        heading = CHAPTER_RE.match(text)
        if heading:
            finish(chapter)
            number = heading.group(1)
            if number in seen_chapters:
                raise PlanError(path, n, f"duplicate chapter number {number}")
            seen_chapters.add(number)
            chapter = Chapter(number, heading.group(2).strip(), None, None, [], line=n)
            book.chapters.append(chapter)
            continue
        if chapter is None:
            header = HEADER_RE.match(text)
            if header:
                setattr(book, header.group(1), header.group(2).strip())
                continue
            raise PlanError(path, n, f"unrecognised line before the first chapter: {stripped}")
        fieldline = FIELD_RE.match(text)
        if fieldline:
            name, value = fieldline.group(1), fieldline.group(2).strip()
            if getattr(chapter, name) is not None:
                raise PlanError(path, n, f"second '{name}:' line in chapter {chapter.number}")
            if name == "read":
                if value not in READ_VALUES:
                    raise PlanError(path, n, f"read must be yes, no or unasked, not '{value}'")
                chapter.read_line = n
            setattr(chapter, name, value)
            continue
        if text.startswith("- ["):
            concept = CONCEPT_RE.match(text)
            if not concept:
                raise PlanError(path, n, "concept lines look like '- [ ] 2.5 Title'")
            mark, cid, title = concept.groups()
            if mark not in STATE_BY_MARK:
                raise PlanError(path, n, f"unknown marker [{mark}]; use [ ], [>], [!] or [x]")
            if cid in seen_ids:
                raise PlanError(path, n, f"duplicate concept id {cid} (first on line {seen_ids[cid]})")
            seen_ids[cid] = n
            state = STATE_BY_MARK[mark]
            if state == "current":
                if current_at is not None:
                    raise PlanError(
                        path, n, f"a second concept in progress [>] (first on line {current_at})"
                    )
                current_at = n
            chapter.concepts.append(Concept(cid, title.strip(), state, line=n))
            continue
        raise PlanError(path, n, f"unrecognised line: {stripped}")

    if not book.title:
        raise PlanError(path, 1, "no book title ('# Title')")
    if not book.chapters:
        raise PlanError(path, 1, "no chapters ('## 1. Title')")
    finish(chapter)
    return book


def all_concepts(book):
    return [c for ch in book.chapters for c in ch.concepts]


def next_concept(book):
    """The concept in progress, else the first not started one, else None."""
    concepts = all_concepts(book)
    for c in concepts:
        if c.state == "current":
            return c
    for c in concepts:
        if c.state == "todo":
            return c
    return None


def chapter_of(book, concept):
    for ch in book.chapters:
        if concept in ch.concepts:
            return ch
    return None


def quiz_size(book):
    reviewable = sum(c.state in ("done", "shaky") for c in all_concepts(book))
    return min(MAX_QUIZ, reviewable)


def fit(text, width):
    """Truncate text to width characters, ending in an ellipsis when cut."""
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "…"


def chapter_symbol(ch, is_next_chapter):
    states = [c.state for c in ch.concepts]
    if all(s == "done" for s in states):
        return "✓"
    if is_next_chapter:
        return "▶"
    if "shaky" in states:
        return "!"
    return "·"


def concept_symbol(c):
    return {"done": "✓", "current": "▶", "shaky": "!", "todo": "·"}[c.state]


def render_map(book, width=80):
    concepts = all_concepts(book)
    total = len(concepts)
    done = sum(c.state == "done" for c in concepts)
    shaky = sum(c.state == "shaky" for c in concepts)
    chapters_done = sum(all(c.state == "done" for c in ch.concepts) for ch in book.chapters)
    nxt = next_concept(book)
    next_chapter = chapter_of(book, nxt) if nxt else None

    filled = round(BAR_CELLS * done / total) if total else 0
    bar = "█" * filled + "░" * (BAR_CELLS - filled)
    stats = f"{chapters_done} of {len(book.chapters)} chapters · {done} of {total} concepts"
    title = fit(book.title, width - len(bar) - len(stats) - 3)
    lines = [f"{title}  {bar} {stats}" if title else f"{bar} {stats}", ""]

    number_width = max(len(ch.number) for ch in book.chapters)
    prefix_width = len(f" ✓ Ch {'':<{number_width}}  ")
    count_width = max(len(f"{len(ch.concepts)}/{len(ch.concepts)} concepts") for ch in book.chapters)
    title_width = width - prefix_width - 2 - count_width
    concept_indent = " " * prefix_width
    concept_title_cap = width - prefix_width - 2 - 2 - len(SHAKY_NOTE)

    for ch in book.chapters:
        ch_done = sum(c.state == "done" for c in ch.concepts)
        is_next = ch is next_chapter
        symbol = chapter_symbol(ch, is_next)
        count = f"{ch_done}/{len(ch.concepts)} concepts"
        lines.append(
            f" {symbol} Ch {ch.number:<{number_width}}  "
            f"{fit(ch.title, title_width):<{title_width}}  {count:>{count_width}}"
        )
        if not is_next:
            continue
        column = min(concept_title_cap, max(len(c.title) for c in ch.concepts))
        for c in ch.concepts:
            note = ""
            if c is nxt:
                note = YOU_ARE_HERE if c.state == "current" else UP_NEXT
            elif c.state == "shaky":
                note = SHAKY_NOTE
            row = f"{concept_indent}{concept_symbol(c)} {fit(c.title, column):<{column}}"
            lines.append(f"{row}  {note}" if note else row.rstrip())

    lines.append("")
    quiz = quiz_size(book)
    if nxt is None:
        if shaky:
            plural = "concept" if shaky == 1 else "concepts"
            lines.append(f"Book complete · {shaky} shaky {plural} to re-quiz")
        else:
            lines.append("Book complete")
    else:
        lead = "Next session: "
        if quiz:
            lead += f"{quiz}-question warm-up quiz, then "
        lines.append(lead + fit(nxt.title, width - len(lead)))
    return "\n".join(lines)


def plan_path(book_dir):
    p = Path(book_dir).expanduser()
    return p if p.is_file() else p / "plan.md"


def cmd_progress(args):
    print(render_map(parse_plan(plan_path(args.book_dir))))


def build_parser():
    parser = argparse.ArgumentParser(prog="lbr.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("progress", help="print the progress map of a book")
    p.add_argument("book_dir")
    p.set_defaults(func=cmd_progress)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except PlanError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
