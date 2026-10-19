import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from campusflow.storage import load_tickets, save_tickets


def make_ticket(ticket_id="T001", notes=None):
    """Return a valid ticket for storage tests."""
    return {
        "id": ticket_id,
        "title": "Network connection issue",
        "category": "Network",
        "urgency": "medium",
        "affected_users": 3,
        "priority": "medium",
        "status": "open",
        "assigned_to": None,
        "notes": [] if notes is None else notes,
    }


class TestStorage(unittest.TestCase):

    def test_missing_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            self.assertEqual(load_tickets(path), [])

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            tickets = [make_ticket()]

            save_tickets(tickets, path)

            self.assertEqual(load_tickets(path), tickets)

    def test_malformed_json_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            path.write_text("{invalid json", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "malformed"):
                load_tickets(path)

    def test_non_list_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            path.write_text('{"ticket": "T001"}', encoding="utf-8")

            with self.assertRaises(ValueError):
                load_tickets(path)

    def test_duplicate_ticket_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            tickets = [make_ticket("T001"), make_ticket("T001")]
            path.write_text(json.dumps(tickets), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate ticket ID"):
                load_tickets(path)

    def test_invalid_note_structure_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            ticket = make_ticket(notes=[{"message": "Missing required fields"}])
            path.write_text(json.dumps([ticket]), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_tickets(path)

    def test_invalid_collection_does_not_mutate_original_tickets(self):
        ticket = make_ticket(notes=[{"message": "Invalid note structure"}])
        original = json.loads(json.dumps([ticket]))

        with self.assertRaises(ValueError):
            save_tickets([ticket], "unused-test-file.json")

        self.assertEqual([ticket], original)

    def test_ticket_id_continues_after_reload(self):
        from campusflow.tickets import create_ticket

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            tickets = [make_ticket("T004")]
            save_tickets(tickets, path)
            loaded = load_tickets(path)

            new_ticket = create_ticket(
                loaded, "Printer issue", "Hardware", "low", 1
            )

            self.assertEqual(new_ticket["id"], "T005")

    def test_note_id_continues_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            ticket = make_ticket(notes=[
                {
                    "note_id": "N001",
                    "author": "Reuben",
                    "message": "Contacted the network team",
                },
            ])
            save_tickets([ticket], path)
            loaded = load_tickets(path)

            from campusflow.workflow import add_note

            note = add_note(
                "T001", "Gongbede", "Waiting for a response", loaded
            )

            self.assertEqual(note["note_id"], "N002")

    def test_failed_save_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            path.write_text('[{"existing": true}]', encoding="utf-8")
            original_content = path.read_text(encoding="utf-8")

            with self.assertRaises(ValueError):
                save_tickets([{"id": "T001"}], path)

            self.assertEqual(
                path.read_text(encoding="utf-8"), original_content
            )

    def test_ticket_notes_survive_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            tickets = [
                make_ticket(notes=[
                    {
                        "note_id": "N001",
                        "author": "Reuben",
                        "message": "Contacted the network team",
                    },
                    {
                        "note_id": "N002",
                        "author": "Gongbede",
                        "message": "Waiting for a response",
                    },
                ])
            ]

            save_tickets(tickets, path)
            loaded_tickets = load_tickets(path)

            self.assertEqual(loaded_tickets, tickets)
            self.assertEqual(
                loaded_tickets[0]["notes"], tickets[0]["notes"]
            )


    def test_write_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tickets.json"
            original_content = '[{"original": true}]'
            path.write_text(original_content, encoding="utf-8")

            with patch(
                "campusflow.storage.json.dump",
                side_effect=OSError("simulated disk failure"),
            ):
                with self.assertRaises(OSError):
                    save_tickets([make_ticket()], path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                original_content,
            )

if __name__ == "__main__":
    unittest.main()
