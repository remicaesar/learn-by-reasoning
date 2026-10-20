"""Tests for scripts/lbr.py: the plan parser, the progress map and the CLI."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lbr  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "tamuz_plan.md"
SCRIPT = ROOT / "scripts" / "lbr.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class PlanDir:
    """A temporary book folder holding a plan.md with the given text."""

    def __init__(self, text):
        self.text = text

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.plan = self.dir / "plan.md"
        self.plan.write_text(self.text, encoding="utf-8")
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()


def plan_text(chapters, title="A Book"):
    """Build v1 plan.md text from [(title, [(marker, concept title), ...]), ...]."""
    lines = [lbr.MARKER, f"# {title}", "source: /tmp/book.pdf", "author: Someone", ""]
    for n, (ch_title, concepts) in enumerate(chapters, start=1):
        lines += [f"## {n}. {ch_title}", "pages: 1-2", "read: unasked"]
        for i, (marker, c_title) in enumerate(concepts, start=1):
            lines.append(f"- [{marker}] {n}.{i} {c_title}")
        lines.append("")
    return "\n".join(lines)


def book_from(chapters, title="A Book"):
    with PlanDir(plan_text(chapters, title)) as d:
        return lbr.parse_plan(d.plan)


class ParseTest(unittest.TestCase):
    def test_parse_fixture(self):
        book = lbr.parse_plan(FIXTURE)
        self.assertEqual(len(book.chapters), 10)
        self.assertEqual(book.title, "Undergraduate Game Theory Lecture Notes")
        self.assertEqual(book.author, "Omer Tamuz")
        self.assertTrue(book.source.endswith("ug game theory lectures.pdf"))
        ch2 = book.chapters[1]
        self.assertEqual(ch2.number, "2")
        self.assertEqual(ch2.read, "yes")
        self.assertEqual(ch2.pages, "8-16")
        by_id = {c.id: c for c in ch2.concepts}
        self.assertEqual(by_id["2.5"].state, "current")
        self.assertEqual(by_id["2.5"].title, "Backward induction")
        self.assertEqual(by_id["2.4"].state, "shaky")
        self.assertEqual(by_id["2.1"].state, "done")
        self.assertEqual(by_id["2.6"].state, "todo")


class MapTest(unittest.TestCase):
    def setUp(self):
        self.book = lbr.parse_plan(FIXTURE)
        self.lines = lbr.render_map(self.book).splitlines()

    def test_map_header(self):
        first = self.lines[0]
        total = sum(len(ch.concepts) for ch in self.book.chapters)
        done = sum(c.state == "done" for ch in self.book.chapters for c in ch.concepts)
        self.assertIn("Undergraduate", first)
        self.assertIn("0 of 10 chapters", first)
        self.assertIn(f"{done} of {total} concepts", first)
        filled = round(20 * done / total)
        self.assertIn("█" * filled + "░" * (20 - filled), first)
        self.assertEqual(first.count("█") + first.count("░"), 20)

    def test_map_header_counts_done_chapters(self):
        book = book_from(
            [("One", [("x", "a"), ("x", "b")]), ("Two", [("x", "c"), (" ", "d")])]
        )
        first = lbr.render_map(book).splitlines()[0]
        self.assertIn("1 of 2 chapters", first)
        self.assertIn("3 of 4 concepts", first)
        self.assertIn("█" * 15 + "░" * 5, first)

    def test_map_expands_only_current_chapter(self):
        concept_titles = {
            c.title: ch.number for ch in self.book.chapters for c in ch.concepts
        }
        shown = {
            title: number
            for title, number in concept_titles.items()
            if any(line.strip()[2:].startswith(title) for line in self.lines)
        }
        self.assertTrue(shown)
        self.assertEqual(set(shown.values()), {"2"})
        self.assertEqual(len(shown), 6)
        row_25 = next(line for line in self.lines if "Backward induction" in line)
        self.assertTrue(row_25.endswith("← you are here"), row_25)
        row_24 = next(line for line in self.lines if "Empty threats" in line)
        self.assertIn("shaky", row_24)
        self.assertEqual(sum("← you are here" in line for line in self.lines), 1)

    def test_chapter_symbols(self):
        book = book_from(
            [
                ("Alldone", [("x", "a"), ("x", "b")]),
                ("Holdscurrent", [("x", "c"), (">", "d")]),
                ("Hasshaky", [("!", "e"), ("x", "f")]),
                ("Untouched", [(" ", "g")]),
            ]
        )
        rows = {}
        for line in lbr.render_map(book).splitlines():
            for name in ("Alldone", "Holdscurrent", "Hasshaky", "Untouched"):
                if name in line:
                    rows[name] = line
        self.assertEqual(rows["Alldone"].split()[0], "✓")
        self.assertEqual(rows["Holdscurrent"].split()[0], "▶")
        self.assertEqual(rows["Hasshaky"].split()[0], "!")
        self.assertEqual(rows["Untouched"].split()[0], "·")

    def test_next_chapter_without_current_is_marked(self):
        book = book_from([("One", [("x", "a")]), ("Two", [(" ", "Firstnew"), (" ", "b")])])
        lines = lbr.render_map(book).splitlines()
        row = next(line for line in lines if "Two" in line)
        self.assertEqual(row.split()[0], "▶")
        concept = next(line for line in lines if "Firstnew" in line)
        self.assertIn("← up next", concept)
        self.assertEqual(lines[-1], "Next session: 1-question warm-up quiz, then Firstnew")

    def test_next_session_line(self):
        self.assertEqual(
            self.lines[-1],
            "Next session: 3-question warm-up quiz, then Backward induction",
        )
        one = book_from([("One", [("x", "a"), (">", "Mid")])])
        self.assertEqual(
            lbr.render_map(one).splitlines()[-1],
            "Next session: 1-question warm-up quiz, then Mid",
        )
        none = book_from([("One", [(">", "Fresh"), (" ", "b")])])
        self.assertEqual(lbr.render_map(none).splitlines()[-1], "Next session: Fresh")

    def test_book_complete(self):
        book = book_from([("One", [("x", "a"), ("x", "b")]), ("Two", [("x", "c")])])
        out = lbr.render_map(book)
        self.assertIn("Book complete", out.splitlines()[-1])
        self.assertNotIn("Next session", out)
        self.assertNotIn("you are here", out)
        self.assertIn("2 of 2 chapters", out.splitlines()[0])
        self.assertIn("█" * 20, out.splitlines()[0])

    def test_book_complete_with_shaky(self):
        book = book_from([("One", [("x", "a"), ("!", "b")])])
        last = lbr.render_map(book).splitlines()[-1]
        self.assertTrue(last.startswith("Book complete"), last)
        self.assertIn("1 shaky concept to re-quiz", last)

    def test_truncates_long_names(self):
        long = "An extraordinarily long name that keeps going well past any terminal " * 2
        book = book_from(
            [
                (long, [("x", long), ("!", long + "shaky"), (">", long + "current")]),
                (long, [(" ", long)]),
            ],
            title=long,
        )
        out = lbr.render_map(book)
        for line in out.splitlines():
            self.assertLessEqual(len(line), 80, line)
        self.assertIn("…", out)
        self.assertIn("← you are here", out)
        self.assertIn("shaky", out)
        self.assertIn("1 of 4 concepts", out.splitlines()[0])
        for line in lbr.render_map(self.book).splitlines():
            self.assertLessEqual(len(line), 80, line)


class MalformedTest(unittest.TestCase):
    GOOD = plan_text([("One", [("x", "a"), (" ", "b")])])

    def assert_plan_error(self, text, line_no, fragment):
        with PlanDir(text) as d:
            with self.assertRaises(lbr.PlanError) as ctx:
                lbr.parse_plan(d.plan)
            msg = str(ctx.exception)
            self.assertTrue(msg.startswith(f"{d.plan}:{line_no}: "), msg)
            self.assertIn(fragment, msg)
            result = run_cli("progress", d.dir)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(result.stderr.strip(), msg)
            self.assertEqual(result.stdout, "")

    def test_malformed_plan(self):
        self.assert_plan_error(self.GOOD.replace(lbr.MARKER + "\n", "", 1), 1, "marker")
        self.assert_plan_error(self.GOOD.replace("1.2 b", "1.1 b"), 10, "duplicate")
        self.assert_plan_error(self.GOOD.replace("[ ] 1.2", "[?] 1.2"), 10, "[?]")

    def test_malformed_plan_other_lines(self):
        two_current = self.GOOD.replace("[x] 1.1", "[>] 1.1").replace("[ ] 1.2", "[>] 1.2")
        self.assert_plan_error(two_current, 10, "in progress")
        self.assert_plan_error(self.GOOD.replace("read: unasked", "read: maybe"), 8, "read")
        self.assert_plan_error(self.GOOD.replace("- [ ] 1.2 b", "- [ ]1.2 b"), 10, "concept")
        self.assert_plan_error(self.GOOD + "stray words\n", 11, "unrecognised")

    def test_missing_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("progress", tmp)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("plan.md", result.stderr)


class CliTest(unittest.TestCase):
    def test_progress_prints_map(self):
        result = run_cli("progress", FIXTURE.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, lbr.render_map(lbr.parse_plan(FIXTURE)) + "\n")


if __name__ == "__main__":
    unittest.main()
