"""Checks for public URL resolution (LAN fallback vs explicit HTTPS bases)."""

import unittest

from src.core.config import cors_allowlist, resolve_public_urls


class TestResolvePublicUrls(unittest.TestCase):
    def test_public_host_fallback_derives_lan_ports(self):
        api, ui, redirect = resolve_public_urls("192.168.1.63")
        self.assertEqual(api, "http://192.168.1.63:2006")
        self.assertEqual(ui, "http://192.168.1.63:2007")
        self.assertEqual(redirect, "http://192.168.1.63:2006/auth/gmail/callback")

    def test_explicit_https_bases_win(self):
        api, ui, redirect = resolve_public_urls(
            "localhost",
            "https://server-trackmyspend.nigmulabs.xyz/",
            "https://trackmyspend.nigmulabs.xyz/",
        )
        self.assertEqual(api, "https://server-trackmyspend.nigmulabs.xyz")
        self.assertEqual(ui, "https://trackmyspend.nigmulabs.xyz")
        self.assertEqual(
            redirect,
            "https://server-trackmyspend.nigmulabs.xyz/auth/gmail/callback",
        )

    def test_cors_includes_frontend_localhost_and_extras(self):
        origins = cors_allowlist(
            "https://trackmyspend.nigmulabs.xyz",
            "http://192.168.1.63:2007, http://100.64.232.11:2007",
        )
        self.assertIn("https://trackmyspend.nigmulabs.xyz", origins)
        self.assertIn("http://localhost:2007", origins)
        self.assertIn("http://127.0.0.1:2007", origins)
        self.assertIn("http://192.168.1.63:2007", origins)
        self.assertIn("http://100.64.232.11:2007", origins)


if __name__ == "__main__":
    unittest.main()
