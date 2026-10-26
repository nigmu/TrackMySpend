import unittest

from src.mail.parse import parse_event


class TestParseEvent(unittest.TestCase):
    def test_partial_is_warning_and_lists_ids(self):
        event_type, severity, message = parse_event(claimed=3, done=1, failed_ids=[4, 9])
        self.assertEqual(event_type, "parse.completed")
        self.assertEqual(severity, "warning")
        self.assertIn("claimed=3", message)
        self.assertIn("done=1", message)
        self.assertIn("failed=2", message)
        self.assertIn("ids=4,9", message)

    def test_all_failed_stays_error(self):
        event_type, severity, message = parse_event(claimed=2, done=0, failed_ids=[1, 2])
        self.assertEqual(event_type, "parse.failed")
        self.assertEqual(severity, "error")
        self.assertIn("ids=1,2", message)

    def test_success_is_info_without_ids(self):
        event_type, severity, message = parse_event(claimed=2, done=2, failed_ids=[])
        self.assertEqual(event_type, "parse.completed")
        self.assertEqual(severity, "info")
        self.assertNotIn("ids=", message)

    def test_ids_are_capped(self):
        _, severity, message = parse_event(claimed=25, done=0, failed_ids=list(range(1, 26)))
        self.assertEqual(severity, "error")
        self.assertIn("ids=" + ",".join(str(i) for i in range(1, 21)), message)
        self.assertIn("+5", message)
        self.assertNotIn(",21", message)
        self.assertNotIn(",25", message)


if __name__ == "__main__":
    unittest.main()
