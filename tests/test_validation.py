import copy
import json
import tempfile
import unittest
from pathlib import Path

from campusflow.storage import (
    load_tickets, load_validated_tickets, save_tickets,
)
from campusflow.validation import validate_ticket_collection
from campusflow.tickets import generate_ticket_id
from campusflow.notes import next_note_id


def good(ticket_id="T001"):
    return {
        "id": ticket_id, "title": "Wi-Fi down", "category": "Network",
        "urgency": "high", "affected_users": 12, "priority": "critical",
        "status": "open", "assigned_to": None, "notes": [],
    }


class TestValidateCollection(unittest.TestCase):

    def test_valid_collection_passes(self):
        self.assertEqual(len(validate_ticket_collection([good(), good("T002")])), 2)

    def test_empty_list_is_valid(self):
        self.assertEqual(validate_ticket_collection([]), [])

    def test_non_list_rejected(self):
        with self.assertRaises(ValueError):
            validate_ticket_collection({"id": "T001"})

    def test_non_dict_record_rejected(self):
        with self.assertRaises(ValueError):
            validate_ticket_collection(["oops"])

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            validate_ticket_collection([good(), good()])

    def test_missing_key_rejected(self):
        bad = good()
        del bad["category"]
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_wrong_priority_rejected(self):
        bad = good()
        bad["priority"] = "low"
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_bad_status_rejected(self):
        bad = good()
        bad["status"] = "banana"
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_bad_category_rejected(self):
        bad = good()
        bad["category"] = "Food"
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_boolean_affected_users_rejected(self):
        bad = good()
        bad["affected_users"] = True
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_in_progress_without_assignee_rejected(self):
        bad = good()
        bad["status"] = "in_progress"
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_bad_note_shape_rejected(self):
        bad = good()
        bad["notes"] = ["plain text note"]
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_duplicate_note_ids_rejected(self):
        bad = good()
        note = {"note_id": "N001", "author": "A", "message": "Long enough"}
        bad["notes"] = [note, dict(note)]
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_old_ticket_without_notes_gets_empty_list(self):
        old = good()
        del old["notes"]
        result = validate_ticket_collection([old])
        self.assertEqual(result[0]["notes"], [])

    def test_input_is_not_modified(self):
        old = good()
        del old["notes"]
        data = [old]
        before = copy.deepcopy(data)
        validate_ticket_collection(data)
        self.assertEqual(data, before)


class TestSafeLoad(unittest.TestCase):

    def test_duplicate_id_file_rejected_and_memory_kept(self):
        memory = [good("T001")]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tickets.json"
            path.write_text(json.dumps([good(), good()]), encoding="utf-8")
            try:
                memory = load_validated_tickets(path)
                self.fail("load should have been rejected")
            except ValueError:
                pass
        self.assertEqual(memory, [good("T001")])

    def test_corrupt_json_rejected_and_memory_kept(self):
        memory = [good("T001")]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tickets.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_validated_tickets(path)
        self.assertEqual(memory, [good("T001")])

    def test_save_and_reload_keeps_notes_and_next_ids(self):
        ticket = good("T005")
        ticket["notes"] = [
            {"note_id": "N001", "author": "A", "message": "First note"},
            {"note_id": "N002", "author": "B", "message": "Second note"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tickets.json"
            save_tickets([ticket], path)
            loaded = load_validated_tickets(path)
        self.assertEqual(loaded, [ticket])
        self.assertEqual(generate_ticket_id(loaded), "T006")
        self.assertEqual(next_note_id(loaded[0]), "N003")

    def test_missing_file_gives_empty_list(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(load_validated_tickets(Path(folder) / "none.json"), [])


if __name__ == "__main__":
    unittest.main()


class TestAffectedUsersEdgeCases(unittest.TestCase):
    def test_zero_affected_users_rejected(self):
        bad = good()
        bad["affected_users"] = 0
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_negative_affected_users_rejected(self):
        bad = good()
        bad["affected_users"] = -1
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_float_affected_users_rejected(self):
        bad = good()
        bad["affected_users"] = 2.5
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])

    def test_string_affected_users_rejected(self):
        bad = good()
        bad["affected_users"] = "12"
        with self.assertRaises(ValueError):
            validate_ticket_collection([bad])
