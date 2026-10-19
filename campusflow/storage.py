
"""Load and save tickets using validated JSON persistence."""

import copy
import json
import os
import tempfile
from pathlib import Path

from campusflow.tickets import (
    calculate_priority,
    validate_affected_users,
    validate_category,
    validate_title,
    validate_urgency,
)

VALID_STATUSES = {"open", "in_progress", "resolved"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def _validate_ticket_collection(tickets):
    """Validate a complete ticket collection without changing the input."""
    if not isinstance(tickets, list):
        raise ValueError("Ticket data must be a JSON list.")

    # Work on a copy so failed validation cannot partially modify the input.
    validated_tickets = copy.deepcopy(tickets)
    seen_ticket_ids = set()

    required_fields = {
        "id",
        "title",
        "category",
        "urgency",
        "affected_users",
        "priority",
        "status",
        "assigned_to",
    }

    for index, ticket in enumerate(validated_tickets):
        location = f"Ticket record {index + 1}"

        if not isinstance(ticket, dict):
            raise ValueError(f"{location} must be a JSON object.")

        missing = required_fields - ticket.keys()
        if missing:
            fields = ", ".join(sorted(missing))
            raise ValueError(
                f"{location} is missing required fields: {fields}."
            )

        ticket_id = ticket["id"]
        if (
            not isinstance(ticket_id, str)
            or len(ticket_id) < 2
            or not ticket_id.startswith("T")
            or not ticket_id[1:].isdigit()
        ):
            raise ValueError(f"{location} has an invalid ticket ID.")

        if ticket_id in seen_ticket_ids:
            raise ValueError(f"Duplicate ticket ID: {ticket_id}.")
        seen_ticket_ids.add(ticket_id)

        try:
            validate_title(ticket["title"])
            category = validate_category(ticket["category"])
            urgency = validate_urgency(ticket["urgency"])
            validate_affected_users(ticket["affected_users"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{location} has invalid ticket data: {exc}"
            ) from exc

        if ticket["category"] != category:
            raise ValueError(
                f"{location} has a non-normalized category."
            )

        if ticket["urgency"] != urgency:
            raise ValueError(
                f"{location} has a non-normalized urgency."
            )

        priority = ticket["priority"]
        if (
            not isinstance(priority, str)
            or priority not in VALID_PRIORITIES
        ):
            raise ValueError(f"{location} has an invalid priority.")

        expected_priority = calculate_priority(
            urgency, ticket["affected_users"]
        )
        if priority != expected_priority:
            raise ValueError(
                f"{location} has an inconsistent priority."
            )

        status = ticket["status"]
        if (
            not isinstance(status, str)
            or status not in VALID_STATUSES
        ):
            raise ValueError(f"{location} has an invalid status.")

        assignee = ticket["assigned_to"]
        if assignee is not None and (
            not isinstance(assignee, str) or not assignee.strip()
        ):
            raise ValueError(f"{location} has an invalid assignee.")

        if status == "in_progress" and assignee is None:
            raise ValueError(
                f"{location} cannot be in progress without an assignee."
            )

        # Older tickets may not have notes. Add the field to the copy only.
        notes = ticket.get("notes", [])
        if not isinstance(notes, list):
            raise ValueError(f"{location} notes must be a list.")

        ticket["notes"] = notes
        seen_note_ids = set()

        for note_index, note in enumerate(notes):
            note_location = (
                f"{location}, note {note_index + 1}"
            )

            if not isinstance(note, dict):
                raise ValueError(
                    f"{note_location} must be a JSON object."
                )

            if set(note) != {"note_id", "author", "message"}:
                raise ValueError(
                    f"{note_location} has an invalid structure."
                )

            note_id = note["note_id"]
            if (
                not isinstance(note_id, str)
                or len(note_id) < 2
                or not note_id.startswith("N")
                or not note_id[1:].isdigit()
            ):
                raise ValueError(
                    f"{note_location} has an invalid note ID."
                )

            if note_id in seen_note_ids:
                raise ValueError(
                    f"{note_location} has duplicate note ID "
                    f"{note_id}."
                )
            seen_note_ids.add(note_id)

            author = note["author"]
            if not isinstance(author, str) or not author.strip():
                raise ValueError(
                    f"{note_location} has an invalid author."
                )

            message = note["message"]
            if not isinstance(message, str):
                raise ValueError(
                    f"{note_location} has an invalid message."
                )

            if not 5 <= len(message.strip()) <= 300:
                raise ValueError(
                    f"{note_location} has an invalid message."
                )

            if message != message.strip():
                raise ValueError(
                    f"{note_location} message is not trimmed."
                )

    return validated_tickets


def load_tickets(path="tickets.json"):
    """Load and validate tickets, or return an empty list if missing."""
    file_path = Path(path)

    if not file_path.exists():
        return []

    try:
        with file_path.open("r", encoding="utf-8") as file:
            tickets = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Cannot read malformed ticket data from {file_path}."
        ) from exc

    return _validate_ticket_collection(tickets)


def save_tickets(tickets, path="tickets.json"):
    """Validate tickets and save safely without damaging an existing file."""
    validated_tickets = _validate_ticket_collection(tickets)
    file_path = Path(path)
    temp_path = None

    try:
        # Keep the temporary file in the same directory so replacement
        # happens on the same filesystem.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(
                validated_tickets,
                file,
                indent=2,
                ensure_ascii=False,
            )
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        # Replace the destination only after the new file is complete.
        os.replace(temp_path, file_path)
        temp_path = None
    finally:
        # Clean up an incomplete temporary file after any failure.
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_validated_tickets(path="tickets.json"):
    """Load AND fully validate tickets. Raises ValueError if anything is wrong.

    Returns a new list only when everything is valid, so the caller's
    current tickets are never touched by a failed load.
    """
    from campusflow.validation import validate_ticket_collection

    return validate_ticket_collection(load_tickets(path))
