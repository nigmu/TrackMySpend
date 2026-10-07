"""apk_url in update.json is a path; the phone receives API_PUBLIC_BASE plus that path."""

import unittest

from src.companion.routes import resolve_apk_url


class TestResolveApkUrl(unittest.TestCase):
    def test_path_is_prefixed(self):
        self.assertEqual(
            resolve_apk_url("/releases/companion-2.0.2.apk", "http://localhost:2006"),
            "http://localhost:2006/releases/companion-2.0.2.apk",
        )

    def test_absolute_url_passes_through(self):
        full = "http://files.example/releases/companion-2.0.2.apk"
        self.assertEqual(resolve_apk_url(full, "http://localhost:2006"), full)

    def test_empty_stays_empty(self):
        self.assertEqual(resolve_apk_url("  ", "http://localhost:2006"), "")


if __name__ == "__main__":
    unittest.main()
