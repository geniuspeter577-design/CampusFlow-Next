import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from main import _print_report, _run_search
from campusflow.cli import ask_valid as real_ask_valid
from campusflow.reports import generate_ticket_report


def make_ticket(ticket_id, title, category, priority, status="open"):
    return {
        "id": ticket_id,
        "title": title,
        "category": category,
        "priority": priority,
        "status": status,
        "assigned_to": None,
    }


class TestMainSearchAndReport(unittest.TestCase):

    def test_sorted_search_uses_priority_then_numeric_ticket_id(self):
        tickets = [
            make_ticket("T010", "Wi-Fi issue", "Network", "high"),
            make_ticket("T002", "Router issue", "Network", "high"),
            make_ticket("T003", "Server outage", "Software", "critical"),
        ]
        output = io.StringIO()

        with patch("main.input", return_value=""), \
                patch("main.ask_valid", return_value=""), \
                redirect_stdout(output):
            _run_search(tickets, sort_by_priority=True)

        result = output.getvalue()
        positions = [
            result.index("T003 |"),
            result.index("T002 |"),
            result.index("T010 |"),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_invalid_search_filter_reprompts_and_applies_valid_filter(self):
        tickets = [
            make_ticket("T001", "Wi-Fi issue", "Network", "high"),
            make_ticket("T002", "Laptop issue", "Hardware", "medium"),
        ]
        output = io.StringIO()
        answers = iter(["invalid-category", "network", "", ""])

        def test_ask_valid(prompt, allowed):
            return real_ask_valid(
                prompt,
                allowed,
                input_func=lambda _: next(answers),
                output_func=lambda message: print(message),
            )

        with patch("main.input", return_value=""), \
                patch("main.ask_valid", side_effect=test_ask_valid), \
                redirect_stdout(output):
            _run_search(tickets)

        result = output.getvalue()
        self.assertIn("Invalid choice.", result)
        self.assertIn("T001 |", result)
        self.assertNotIn("T002 |", result)

    def test_report_output_includes_counts_and_resolution_percentage(self):
        tickets = [
            make_ticket("T001", "Wi-Fi issue", "Network", "high", "resolved"),
            make_ticket("T002", "Laptop issue", "Hardware", "medium", "open"),
        ]
        report = generate_ticket_report(tickets)
        output = io.StringIO()

        with redirect_stdout(output):
            _print_report(report)

        result = output.getvalue()
        self.assertIn("Total tickets: 2", result)
        self.assertIn("Unresolved: 1 | Resolved: 1", result)
        self.assertIn("Resolution: 50.0%", result)
        self.assertIn("Network: 1", result)
        self.assertIn("Hardware: 1", result)


if __name__ == "__main__":
    unittest.main()
