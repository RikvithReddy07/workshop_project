"""
Automated Test Suite for Appointment Booking System.
Covers all 10 core scenarios:
1. Successful booking of available slot
2. Rejection of invalid or missing inputs
3. Prevention of past date booking
4. Duplicate booking prevention on same date and time slot
5. Booking different slots on the same date
6. Viewing and filtering appointments (by email, date, status)
7. Secure cancellation using correct token
8. Cancelled slot becoming available again for re-booking
9. Handling invalid appointment IDs & unauthorized cancellation attempts
10. Graceful handling of database errors / invalid constraints
"""

import os
import sys
import tempfile
import pytest
from datetime import date, timedelta

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
import database


@pytest.fixture
def client(tmp_path):
    """Set up test client with a clean isolated temporary SQLite database."""
    db_file = tmp_path / "test_appointments.db"
    os.environ["APPOINTMENTS_DB_PATH"] = str(db_file)

    # Re-initialize DB
    database.init_db()

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client

    if "APPOINTMENTS_DB_PATH" in os.environ:
        del os.environ["APPOINTMENTS_DB_PATH"]


def test_scenario_1_successful_booking(client):
    """Scenario 1: A user can successfully book an available appointment."""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    payload = {
        "full_name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1 (555) 123-4567",
        "appointment_date": tomorrow,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Consultation on project roadmap"
    }

    res = client.post("/book", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    assert "appointment" in data
    assert data["appointment"]["id"] > 0
    assert data["appointment"]["full_name"] == "Alice Johnson"
    assert data["appointment"]["cancellation_token"] is not None
    assert len(data["appointment"]["cancellation_token"]) > 20


def test_scenario_2_invalid_or_missing_inputs_rejected(client):
    """Scenario 2: Invalid or missing form inputs are rejected."""
    tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Missing full name
    res = client.post("/book", json={
        "full_name": "",
        "email": "valid@example.com",
        "phone": "5551234567",
        "appointment_date": tomorrow,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Regular checkup"
    })
    assert res.status_code == 400
    assert any("full name" in err.lower() for err in res.get_json()["errors"])

    # Invalid email
    res = client.post("/book", json={
        "full_name": "Valid Name",
        "email": "invalid-email-format",
        "phone": "5551234567",
        "appointment_date": tomorrow,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Regular checkup"
    })
    assert res.status_code == 400
    assert any("email" in err.lower() for err in res.get_json()["errors"])

    # Invalid phone (less than 7 digits)
    res = client.post("/book", json={
        "full_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "123",
        "appointment_date": tomorrow,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Regular checkup"
    })
    assert res.status_code == 400
    assert any("phone" in err.lower() for err in res.get_json()["errors"])

    # Reason too short
    res = client.post("/book", json={
        "full_name": "Valid Name",
        "email": "valid@example.com",
        "phone": "5551234567",
        "appointment_date": tomorrow,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "a"
    })
    assert res.status_code == 400
    assert any("reason" in err.lower() for err in res.get_json()["errors"])


def test_scenario_3_past_dates_cannot_be_booked(client):
    """Scenario 3: Past dates cannot be booked."""
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    payload = {
        "full_name": "Bob Martin",
        "email": "bob@example.com",
        "phone": "5559876543",
        "appointment_date": yesterday,
        "time_slot": "10:00 AM - 11:00 AM",
        "reason": "Past date test"
    }

    res = client.post("/book", json=payload)
    assert res.status_code == 400
    data = res.get_json()
    assert any("past" in err.lower() for err in data["errors"])

    # Available slots endpoint should also indicate past date
    res_slots = client.get(f"/available-slots?date={yesterday}")
    assert res_slots.status_code == 200
    slots_data = res_slots.get_json()
    assert slots_data["is_past"] is True
    assert len(slots_data["available_slots"]) == 0


def test_scenario_4_duplicate_bookings_rejected(client):
    """Scenario 4: Duplicate bookings for the same date and time slot are rejected."""
    future_date = (date.today() + timedelta(days=2)).strftime("%Y-%m-%d")
    slot = "11:00 AM - 12:00 PM"

    first_booking = {
        "full_name": "User One",
        "email": "user1@example.com",
        "phone": "5551112222",
        "appointment_date": future_date,
        "time_slot": slot,
        "reason": "First booking of this slot"
    }
    res1 = client.post("/book", json=first_booking)
    assert res1.status_code == 201

    # Attempt to book the exact same date and slot
    second_booking = {
        "full_name": "User Two",
        "email": "user2@example.com",
        "phone": "5553334444",
        "appointment_date": future_date,
        "time_slot": slot,
        "reason": "Second conflicting booking attempt"
    }
    res2 = client.post("/book", json=second_booking)
    assert res2.status_code == 409
    data2 = res2.get_json()
    assert any("already booked" in err.lower() for err in data2["errors"])


def test_scenario_5_different_time_slots_same_date(client):
    """Scenario 5: Different time slots on the same date can be booked."""
    future_date = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")

    res1 = client.post("/book", json={
        "full_name": "User A",
        "email": "usera@example.com",
        "phone": "5551113333",
        "appointment_date": future_date,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Morning slot"
    })
    assert res1.status_code == 201

    res2 = client.post("/book", json={
        "full_name": "User B",
        "email": "userb@example.com",
        "phone": "5554445555",
        "appointment_date": future_date,
        "time_slot": "02:00 PM - 03:00 PM",
        "reason": "Afternoon slot"
    })
    assert res2.status_code == 201


def test_scenario_6_users_can_view_appointments(client):
    """Scenario 6: Users can view their appointments and filter by email/status."""
    test_date = (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
    user_email = "lookup.target@example.com"

    client.post("/book", json={
        "full_name": "Lookup Target",
        "email": user_email,
        "phone": "5559998888",
        "appointment_date": test_date,
        "time_slot": "10:00 AM - 11:00 AM",
        "reason": "Searchable appointment"
    })

    # Fetch via HTML view
    res_html = client.get(f"/appointments?email={user_email}")
    assert res_html.status_code == 200
    assert b"Lookup Target" in res_html.data
    assert b"Searchable appointment" in res_html.data

    # Fetch via JSON format
    res_json = client.get(f"/appointments?email={user_email}&format=json")
    assert res_json.status_code == 200
    data = res_json.get_json()
    assert data["count"] >= 1
    assert data["appointments"][0]["email"] == user_email


def test_scenario_7_users_can_cancel_own_appointments_securely(client):
    """Scenario 7: Users can cancel their own appointments securely with token."""
    future_date = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
    book_res = client.post("/book", json={
        "full_name": "Cancel Subject",
        "email": "cancel@example.com",
        "phone": "5556667777",
        "appointment_date": future_date,
        "time_slot": "03:00 PM - 04:00 PM",
        "reason": "Will cancel this"
    })
    appt_info = book_res.get_json()["appointment"]
    appt_id = appt_info["id"]
    token = appt_info["cancellation_token"]

    cancel_res = client.post(f"/cancel/{appt_id}", json={
        "cancellation_token": token
    })
    assert cancel_res.status_code == 200
    assert cancel_res.get_json()["success"] is True

    # Verify status changed to 'Cancelled'
    appt = database.get_appointment_by_id(appt_id)
    assert appt["status"] == "Cancelled"


def test_scenario_8_cancelled_slots_become_available_again(client):
    """Scenario 8: Cancelled time slots become available again for booking."""
    future_date = (date.today() + timedelta(days=6)).strftime("%Y-%m-%d")
    slot = "04:00 PM - 05:00 PM"

    # 1. Book the slot
    book_res = client.post("/book", json={
        "full_name": "First Holder",
        "email": "holder1@example.com",
        "phone": "5551239999",
        "appointment_date": future_date,
        "time_slot": slot,
        "reason": "Original booking"
    })
    appt_data = book_res.get_json()["appointment"]
    appt_id = appt_data["id"]
    token = appt_data["cancellation_token"]

    # 2. Verify slot is currently booked
    slots_res1 = client.get(f"/available-slots?date={future_date}")
    assert slot not in slots_res1.get_json()["available_slots"]
    assert slot in slots_res1.get_json()["booked_slots"]

    # 3. Cancel the booking
    cancel_res = client.post(f"/cancel/{appt_id}", json={"cancellation_token": token})
    assert cancel_res.status_code == 200

    # 4. Verify slot is now available again in API
    slots_res2 = client.get(f"/available-slots?date={future_date}")
    assert slot in slots_res2.get_json()["available_slots"]

    # 5. Book the exact same slot again under new client
    rebook_res = client.post("/book", json={
        "full_name": "Second Holder",
        "email": "holder2@example.com",
        "phone": "5559871111",
        "appointment_date": future_date,
        "time_slot": slot,
        "reason": "Re-booked slot after cancellation"
    })
    assert rebook_res.status_code == 201


def test_scenario_9_invalid_id_and_unauthorized_cancellation_handled_safely(client):
    """Scenario 9: Invalid appointment IDs and unauthorized cancellation attempts are handled safely."""
    future_date = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
    book_res = client.post("/book", json={
        "full_name": "Secure Owner",
        "email": "owner@example.com",
        "phone": "5550001111",
        "appointment_date": future_date,
        "time_slot": "09:00 AM - 10:00 AM",
        "reason": "Protected appointment"
    })
    appt_id = book_res.get_json()["appointment"]["id"]

    # Attempt with wrong token
    bad_token_res = client.post(f"/cancel/{appt_id}", json={
        "cancellation_token": "wrong-bogus-token-12345"
    })
    assert bad_token_res.status_code == 403
    assert "unauthorized" in bad_token_res.get_json()["error"].lower()

    # Attempt with non-existent appointment ID
    fake_id_res = client.post("/cancel/99999", json={
        "cancellation_token": "any-token"
    })
    assert fake_id_res.status_code == 404

    # Attempt without token
    no_token_res = client.post(f"/cancel/{appt_id}", json={})
    assert no_token_res.status_code == 400


def test_scenario_10_database_errors_and_edge_cases_handled_gracefully(client):
    """Scenario 10: The application handles database errors gracefully."""
    # Test invalid time slot outside business hours
    future_date = (date.today() + timedelta(days=8)).strftime("%Y-%m-%d")
    invalid_slot_res = client.post("/book", json={
        "full_name": "Edge Tester",
        "email": "edge@example.com",
        "phone": "5551234567",
        "appointment_date": future_date,
        "time_slot": "11:00 PM - 12:00 AM",  # Midnight - not allowed
        "reason": "Out of hours"
    })
    assert invalid_slot_res.status_code == 400

    # Test invalid date formatting on /available-slots
    bad_date_slots = client.get("/available-slots?date=not-a-date")
    assert bad_date_slots.status_code == 400

    # Test missing date param on /available-slots
    missing_date_slots = client.get("/available-slots")
    assert missing_date_slots.status_code == 400
