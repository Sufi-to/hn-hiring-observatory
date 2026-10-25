"""Test ingestion parsing without requiring a Databricks runtime."""
import ast
import html
import re
import unittest
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


def load_parsers():
    source = Path("notebooks/01_ingest_hn.py").read_text()
    module = ast.parse(source)
    definitions = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                   and node.name in {"PlainText", "clean_html", "is_hiring_thread"}]
    namespace = dict(html=html, re=re, HTMLParser=HTMLParser,
                     START=int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()))
    exec(compile(ast.Module(body=definitions, type_ignores=[]), "parsers", "exec"), namespace)
    return namespace


class IngestionParsingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsers = load_parsers()

    def test_html_preserves_role_boundaries_and_salary_symbols(self):
        cleaned = self.parsers["clean_html"]("Acme<p>Senior C++ &amp; Rust<br>$120k–$180k &lt;5 years")
        self.assertEqual(cleaned, "Acme\nSenior C++ & Rust\n$120k–$180k <5 years")

    def test_discovery_excludes_other_monthly_threads_and_impersonation(self):
        base = dict(type="story", by="whoishiring", time=1609502400)
        accept = self.parsers["is_hiring_thread"]
        self.assertTrue(accept(dict(base, title="Ask HN: Who is hiring? (January 2021)")))
        for title in ["Ask HN: Who wants to be hired? (January 2021)",
                      "Ask HN: Freelancer? Seeking freelancer? (January 2021)",
                      "Ask HN: Who is hiring? unrelated discussion"]:
            self.assertFalse(accept(dict(base, title=title)))
        self.assertFalse(accept(dict(base, title="Ask HN: Who is hiring? (January 2021)", by="other")))
        self.assertFalse(accept(dict(base, title="Ask HN: Who is hiring? (January 2021)", deleted=True)))
        self.assertFalse(accept(dict(base, title="Ask HN: Who is hiring? (January 2019)", time=1546344000)))


if __name__ == "__main__":
    unittest.main()
