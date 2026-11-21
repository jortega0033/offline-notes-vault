"""Static checks on the three browser files (read as text only)."""

import re
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "notes_vault" / "static"


def read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


class StaticAssetsTest(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")
        self.css = read("app.css")
        self.js = read("app.js")

    def test_no_external_urls(self):
        for name, text in (("html", self.html), ("css", self.css), ("js", self.js)):
            with self.subTest(file=name):
                self.assertIsNone(re.search(r"(?i)\b(?:https?|ftp|wss?):", text))
                self.assertIsNone(re.search(r"""(?i)(?:src|href|url\()\s*=?\s*["']?//""", text))
                self.assertNotIn("@import", text)

    def test_no_inline_script_style_or_handlers(self):
        for m in re.finditer(r"(?is)<script\b([^>]*)>(.*?)</script>", self.html):
            self.assertIn("src=", m.group(1))
            self.assertEqual(m.group(2).strip(), "")
        self.assertIsNone(re.search(r"(?i)<style\b", self.html))
        self.assertIsNone(re.search(r"(?i)\sstyle\s*=", self.html))
        self.assertIsNone(re.search(r"(?i)\son[a-z]+\s*=", self.html))
        self.assertIsNone(re.search(r"(?i)javascript:", self.html))

    def test_js_avoids_unsafe_sinks(self):
        for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(bad, self.js)

    def test_required_ids(self):
        ids = [
            "search", "new-note", "note-list", "load-sample", "note-title", "note-body",
            "body-count", "save", "status", "conflict", "conflict-reload",
            "conflict-overwrite", "conflict-mine", "preview",
        ]
        for i in ids:
            with self.subTest(id=i):
                self.assertEqual(len(re.findall(r'\bid="%s"' % re.escape(i), self.html)), 1)

    def test_labels_and_landmarks(self):
        self.assertIn('lang="en"', self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertIn("<title>Offline Notes Vault</title>", self.html)
        self.assertRegex(self.html, r'<label for="search">Search notes</label>')
        self.assertRegex(self.html, r'<label for="note-title">Note title</label>')
        self.assertRegex(self.html, r'<label for="note-body">Note text</label>')
        self.assertIn('<input type="search" id="search"', self.html)
        self.assertRegex(self.html, r'<nav aria-label="Notes"')
        self.assertRegex(self.html, r'id="note-title" maxlength="200"')
        self.assertNotRegex(self.html, r'id="note-body"[^>]*maxlength')
        self.assertRegex(self.html, r'id="status"[^>]*role="status"')
        self.assertRegex(self.html, r'id="status"[^>]*aria-live="polite"')
        self.assertRegex(self.html, r'id="conflict"[^>]*role="alert"')
        self.assertIn('aria-label="Your unsaved text"', self.html)
        self.assertEqual(len(re.findall(r"<h1\b", self.html)), 1)
        for tag in ("<header", "<main"):
            self.assertIn(tag, self.html)
        for text in ("New note", "Load sample note", "Save", "Load latest into editor",
                     "Save mine as a new revision"):
            self.assertIn(">%s<" % text, self.html)
        self.assertIn("Plain text preview", self.html)

    def test_focus_and_reduced_motion_css(self):
        self.assertIn(":focus-visible", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("min-width: 760px", self.css)


if __name__ == "__main__":
    unittest.main()
