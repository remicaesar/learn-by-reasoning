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
        total = sum(len(ch.concepts) for ch in self.book.chapters)
        done = sum(c.state == "done" for ch in self.book.chapters for c in ch.concepts)
        self.assertEqual(self.lines[0], "Undergraduate Game Theory Lecture Notes")
        filled = round(20 * done / total)
        self.assertEqual(
            self.lines[1],
            "█" * filled + "░" * (20 - filled) + f" 0 of 10 chapters · {done} of {total} concepts",
        )
        self.assertEqual(self.lines[2], "")

    def test_map_header_truncates_long_title_to_width(self):
        title = "T" * 100
        first = lbr.render_map(book_from([("One", [(" ", "a")])], title=title)).splitlines()[0]
        self.assertEqual(first, "T" * 79 + "…")
        self.assertEqual(len(first), 80)

    def test_map_header_counts_done_chapters(self):
        book = book_from(
            [("One", [("x", "a"), ("x", "b")]), ("Two", [("x", "c"), (" ", "d")])]
        )
        first = lbr.render_map(book).splitlines()[1]
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
        self.assertIn("2 of 2 chapters", out.splitlines()[1])
        self.assertIn("█" * 20, out.splitlines()[1])

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
        self.assertIn("1 of 4 concepts", out.splitlines()[1])
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


class SetStateTest(unittest.TestCase):
    def setUp(self):
        self.d = PlanDir(FIXTURE.read_text(encoding="utf-8")).__enter__()
        self.addCleanup(self.d.__exit__)
        self.before = self.d.plan.read_bytes()

    def changed_lines(self):
        old = self.before.decode("utf-8").splitlines(keepends=True)
        new = self.d.plan.read_bytes().decode("utf-8").splitlines(keepends=True)
        self.assertEqual(len(old), len(new))
        return [(i + 1, a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b]

    def state_of(self, cid):
        book = lbr.parse_plan(self.d.plan)
        return next(c.state for c in lbr.all_concepts(book) if c.id == cid)

    def test_set_state_rewrites_one_line(self):
        lbr.set_state(self.d.plan, "2.6", "done")
        self.assertEqual(
            self.changed_lines(),
            [(20, "- [ ] 2.6 One deviation principle\n", "- [x] 2.6 One deviation principle\n")],
        )

    def test_set_state_keeps_crlf(self):
        self.d.plan.write_bytes(self.before.replace(b"\n", b"\r\n"))
        self.before = self.d.plan.read_bytes()
        lbr.set_state(self.d.plan, "1.2", "shaky")
        self.assertEqual(
            self.d.plan.read_bytes(),
            self.before.replace(b"- [ ] 1.2 Strategy", b"- [!] 1.2 Strategy"),
        )

    def test_set_current_demotes_previous(self):
        lbr.set_state(self.d.plan, "3.1", "current")
        self.assertEqual(self.state_of("3.1"), "current")
        self.assertEqual(self.state_of("2.5"), "todo")
        self.assertEqual([n for n, _, _ in self.changed_lines()], [19, 25])
        lbr.set_state(self.d.plan, "3.1", "current")
        self.assertEqual(self.state_of("3.1"), "current")

    def test_set_current_leaves_done_and_shaky(self):
        lbr.set_state(self.d.plan, "2.5", "done")
        lbr.set_state(self.d.plan, "2.6", "current")
        self.assertEqual(self.state_of("2.5"), "done")
        self.assertEqual(self.state_of("2.4"), "shaky")
        self.assertEqual(self.state_of("2.1"), "done")

    def test_set_unknown_id_refused(self):
        with self.assertRaises(lbr.PlanError) as ctx:
            lbr.set_state(self.d.plan, "9.9", "done")
        self.assertIn("9.9", str(ctx.exception))
        result = run_cli("set", self.d.dir, "9.9", "done")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no concept with id 9.9", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        result = run_cli("set", self.d.dir, "2.6", "finished")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.d.plan.read_bytes(), self.before)

    def test_set_keeps_file_on_error(self):
        broken = self.before.replace(b"- [ ] 1.2", b"- [>] 1.2")
        self.d.plan.write_bytes(broken)
        with self.assertRaises(lbr.PlanError):
            lbr.set_state(self.d.plan, "2.6", "done")
        self.assertEqual(self.d.plan.read_bytes(), broken)
        result = run_cli("set", self.d.dir, "2.6", "done")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.d.plan.read_bytes(), broken)
        with self.assertRaises(ValueError):
            lbr.set_state(self.d.plan, "2.6", "finished")
        self.assertEqual(self.d.plan.read_bytes(), broken)
        self.assertEqual(sorted(p.name for p in self.d.dir.iterdir()), ["plan.md"])

    def test_set_read(self):
        lbr.set_read(self.d.plan, "1", "yes")
        self.assertEqual(self.changed_lines(), [(8, "read: unasked\n", "read: yes\n")])
        self.assertEqual(lbr.parse_plan(self.d.plan).chapters[0].read, "yes")
        result = run_cli("read", self.d.dir, "10", "no")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(lbr.parse_plan(self.d.plan).chapters[9].read, "no")
        for bad in (("11", "yes"), ("1", "unasked")):
            result = run_cli("read", self.d.dir, *bad)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(lbr.parse_plan(self.d.plan).chapters[0].read, "yes")


class SlugTest(unittest.TestCase):
    def test_slugify_turkish(self):
        self.assertEqual(lbr.slugify("Oyun Kuramı: Giriş"), "oyun-kurami-giris")
        self.assertEqual(lbr.slugify("Çağdaş Öğütler, Üç İşçi"), "cagdas-ogutler-uc-isci")
        self.assertEqual(lbr.slugify("Économie & Société"), "economie-societe")
        self.assertEqual(lbr.slugify("Undergraduate Game Theory"), "undergraduate-game-theory")
        self.assertEqual(lbr.slugify("!!!"), "book")
        result = run_cli("slug", "Oyun Kuramı: Giriş")
        self.assertEqual(result.stdout, "oyun-kurami-giris\n")

    def test_turkish_title_renders(self):
        book = book_from([("Bölüm Şu", [(">", "Çağrı öğesi")])], title="Oyun Kuramı: Giriş")
        out = lbr.render_map(book)
        self.assertIn("Oyun Kuramı", out)
        self.assertIn("Çağrı öğesi", out)
        with PlanDir(plan_text([("Bölüm", [(" ", "Öğe")])], title="Oyun Kuramı")) as d:
            result = run_cli("progress", d.dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Oyun Kuramı", result.stdout)


class FindBooksTest(unittest.TestCase):
    def test_find_books_ignores_unmarked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "marked").mkdir()
            (root / "marked" / "plan.md").write_text(plan_text([("One", [("x", "a"), (" ", "b")])]), encoding="utf-8")
            (root / "unmarked").mkdir()
            (root / "unmarked" / "plan.md").write_text("# Some other plan\n- [ ] 1.1 a\n", encoding="utf-8")
            (root / "empty").mkdir()
            (root / "loose.md").write_text(lbr.MARKER + "\n", encoding="utf-8")
            books = lbr.find_books(root)
            self.assertEqual([p.name for p, _ in books], ["marked"])
            self.assertEqual(books[0][1].title, "A Book")
            result = run_cli("books", "--root", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout, f"{root / 'marked'}\tA Book\t1 of 2 concepts done\n"
            )

    def test_find_books_missing_root(self):
        missing = Path(tempfile.gettempdir()) / "lbr-no-such-root"
        self.assertEqual(lbr.find_books(missing), [])
        result = run_cli("books", "--root", missing)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No books", result.stdout)


class StatusTest(unittest.TestCase):
    def test_status_lines(self):
        result = run_cli("status", FIXTURE.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "next: 2.5 Backward induction",
                "quiz: 3",
                "shaky: 2.4",
                "done: 1.1,2.1,2.2,2.3",
                "read: 2 yes",
            ],
        )

    def test_status_without_current_or_reviews(self):
        with PlanDir(plan_text([("One", [(" ", "a")]), ("Two", [(" ", "b")])])) as d:
            self.assertEqual(
                run_cli("status", d.dir).stdout.splitlines(),
                ["next: 1.1 a", "quiz: 0", "shaky: -", "done: -", "read: 1 unasked"],
            )

    def test_status_complete(self):
        with PlanDir(plan_text([("One", [("x", "a"), ("!", "b")])])) as d:
            self.assertEqual(
                run_cli("status", d.dir).stdout.splitlines(),
                ["next: -", "quiz: 2", "shaky: 1.2", "done: 1.1", "read: -"],
            )


if __name__ == "__main__":
    unittest.main()
