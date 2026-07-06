import unittest

from app.utils.video_ideas_csv import parse_ideas_csv


class TestVideoIdeasCsv(unittest.TestCase):
    def test_parse_valid_csv(self):
        content = """category,theme,script,keywords,generated_at
finances,Tema teste,Roteiro curto para o video.,"wallet, money, savings",2026-01-01
"""
        rows = parse_ideas_csv(content)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["theme"], "Tema teste")
        self.assertEqual(rows[0]["script"], "Roteiro curto para o video.")
        self.assertEqual(rows[0]["keywords"], "wallet, money, savings")

    def test_parse_rejects_missing_columns(self):
        with self.assertRaises(ValueError):
            parse_ideas_csv("theme,script\nA,B")

    def test_parse_skips_empty_rows(self):
        content = """theme,script,keywords
Tema 1,Script 1,"a, b, c, d, e"

Tema 2,Script 2,"f, g, h, i, j"
"""
        rows = parse_ideas_csv(content)
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
