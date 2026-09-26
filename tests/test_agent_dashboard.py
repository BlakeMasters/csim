"""Status and HTML checks for the read-only agent work board."""
import unittest

from agent_dashboard import render_dashboard, status_kind


class AgentDashboardTests(unittest.TestCase):
    def test_qualified_done_statuses_count_as_completed(self):
        for value in ("Done", "Done as reference tests", "Done for supplied matrix",
                      "Done descriptively", "Complete", "Completed"):
            with self.subTest(value=value):
                self.assertEqual(status_kind(value), "done")
        self.assertEqual(status_kind("In progress"), "active")
        self.assertEqual(status_kind("Done-ish draft"), "other")

    def test_render_counts_qualified_done_and_escapes_board_text(self):
        board = {"updated": "2026-09-26 21:00 UTC", "tasks": [
            {"ID": "A", "Work": "<script>alert(1)</script>",
             "Status": "Done as reference", "Owner": "agent",
             "Evidence / next action": "<img src=x onerror=alert(1)>"},
            {"ID": "B", "Work": "Second result", "Status": "Done for scope",
             "Owner": "agent", "Evidence / next action": "Checked"},
            {"ID": "C", "Work": "Current task", "Status": "In progress",
             "Owner": "agent", "Evidence / next action": "Running"},
        ], "activity": []}
        page = render_dashboard(board, "2026-09-26 21:01 UTC")
        self.assertIn('<strong>2</strong><span>Done</span>', page)
        self.assertIn('<strong>1</strong><span>Working</span>', page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertNotIn("<script>", page)


if __name__ == "__main__":
    unittest.main()
