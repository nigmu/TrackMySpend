"""Checks for public URL resolution (LAN fallback vs explicit bases)."""

import unittest

from src.core.config import cors_allowlist, resolve_public_urls


class TestResolvePublicUrls(unittest.TestCase):
    def test_public_host_fallback_derives_lan_ports(self):
        api, ui = resolve_public_urls("homeserver")
        self.assertEqual(api, "http://homeserver:2006")
        self.assertEqual(ui, "http://homeserver:2007")

    def test_explicit_bases_win(self):
        api, ui = resolve_public_urls(
            "localhost",
            "http://localhost:2006/",
            "http://localhost:2007/",
        )
        self.assertEqual(api, "http://localhost:2006")
        self.assertEqual(ui, "http://localhost:2007")

    def test_cors_includes_frontend_localhost_and_extras(self):
        origins = cors_allowlist(
            "http://localhost:2007",
            "http://homeserver:2007, http://tailscale-host:2007",
        )
        self.assertIn("http://localhost:2007", origins)
        self.assertIn("http://localhost:2007", origins)
        self.assertIn("http://127.0.0.1:2007", origins)
        self.assertIn("http://homeserver:2007", origins)
        self.assertIn("http://tailscale-host:2007", origins)


if __name__ == "__main__":
    unittest.main()
