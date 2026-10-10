"""
Flask Application for Appointment Booking System.
Provides RESTful & template endpoints for:
- Home page dashboard
- Dynamic slot checking
- Appointment booking with validation & concurrency protection
- Appointment viewing and search/filtering
- Secure token-based cancellation
"""

import os
import re
from datetime import datetime, date
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for, flash, abort
)

from database import (
    init_db, seed_sample_data, get_available_slots_for_date,
    book_appointment, get_appointments, get_appointment_by_id,
    cancel_appointment, WORKING_TIME_SLOTS
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-appointment-booking-key-2026")

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$")

def is_valid_phone(phone: str) -> bool:
    """Validate phone number format and ensure 7 to 15 digits."""
    if not phone or not re.match(r"^[+]?[0-9\s\-\.\(\)]{7,25}$", phone.strip()):
        return False
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15

# Initialize database on startup
with app.app_context():
    init_db()
    seed_sample_data()

def validate_booking_data(full_name: str, email: str, phone: str,
                          appointment_date: str, time_slot: str, reason: str) -> list[str]:
    """Validate all booking input fields on the server side."""
    errors = []

    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full Name is required (minimum 2 characters).")
    elif len(full_name.strip()) > 100:
        errors.append("Full Name cannot exceed 100 characters.")

    if not email or not EMAIL_REGEX.match(email.strip()):
        errors.append("A valid email address is required (e.g. user@example.com).")

    if not phone or not is_valid_phone(phone):
        errors.append("A valid phone number is required (7 to 15 digits).")

    # Date validation
    if not appointment_date:
        errors.append("Appointment Date is required.")
    else:
        try:
            parsed_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
            today = date.today()
            if parsed_date < today:
                errors.append("Appointment Date cannot be in the past. Please select today or a future date.")
        except ValueError:
            errors.append("Appointment Date must be in YYYY-MM-DD format.")

    # Time slot validation
    if not time_slot:
        errors.append("Time Slot is required.")
    elif time_slot not in WORKING_TIME_SLOTS:
        errors.append("Selected time slot is outside standard working hours.")

    if not reason or len(reason.strip()) < 3:
        errors.append("Reason for appointment is required (minimum 3 characters).")
    elif len(reason.strip()) > 500:
        errors.append("Reason cannot exceed 500 characters.")

    return errors


@app.route("/")
def index():
    """Home landing page with system overview, statistics, and quick actions."""
    today_str = date.today().strftime("%Y-%m-%d")
    slot_info = get_available_slots_for_date(today_str)
    all_appointments = get_appointments()
    active_count = sum(1 for a in all_appointments if a["status"] == "Booked")

    stats = {
        "today_available": len(slot_info["available_slots"]),
        "today_booked": len(slot_info["booked_slots"]),
        "total_active": active_count,
        "working_slots_count": len(WORKING_TIME_SLOTS),
        "today_date": today_str
    }
    return render_template("index.html", stats=stats)


@app.route("/book", methods=["GET", "POST"])
def book():
    """
    GET: Render the booking form.
    POST: Validate input, verify slot availability, and save appointment.
          Supports both JSON (AJAX) and standard HTML form POST.
    """
    today_str = date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        # Handle JSON or Form-encoded data
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()

        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        appointment_date = data.get("appointment_date", "").strip()
        time_slot = data.get("time_slot", "").strip()
        reason = data.get("reason", "").strip()

        errors = validate_booking_data(
            full_name=full_name,
            email=email,
            phone=phone,
            appointment_date=appointment_date,
            time_slot=time_slot,
            reason=reason
        )

        if errors:
            if request.is_json:
                return jsonify({"success": False, "errors": errors}), 400
            for err in errors:
                flash(err, "danger")
            return render_template(
                "book.html",
                today=today_str,
                working_slots=WORKING_TIME_SLOTS,
                form_data=data
            ), 400

        # Attempt atomic database booking
        app_id, cancel_token, error_msg = book_appointment(
            full_name=full_name,
            email=email,
            phone=phone,
            appointment_date=appointment_date,
            time_slot=time_slot,
            reason=reason
        )

        if error_msg:
            # Slot conflict or DB issue
            status_code = 409 if "already booked" in error_msg.lower() else 500
            if request.is_json:
                return jsonify({"success": False, "errors": [error_msg]}), status_code
            flash(error_msg, "danger")
            return render_template(
                "book.html",
                today=today_str,
                working_slots=WORKING_TIME_SLOTS,
                form_data=data
            ), status_code

        # Booking successful
        success_payload = {
            "success": True,
            "message": "Appointment booked successfully!",
            "appointment": {
                "id": app_id,
                "full_name": full_name,
                "email": email,
                "appointment_date": appointment_date,
                "time_slot": time_slot,
                "reason": reason,
                "cancellation_token": cancel_token
            }
        }

        if request.is_json:
            return jsonify(success_payload), 201

        flash("Appointment booked successfully! Please save your cancellation token.", "success")
        return redirect(url_for("appointments", email=email, token=cancel_token, new_id=app_id))

    # GET request
    selected_date = request.args.get("date", today_str)
    return render_template(
        "book.html",
        today=today_str,
        selected_date=selected_date,
        working_slots=WORKING_TIME_SLOTS,
        form_data={}
    )


@app.route("/available-slots", methods=["GET"])
def available_slots():
    """
    API endpoint: Returns available time slots for a specified date.
    Query param: date (YYYY-MM-DD).
    """
    date_param = request.args.get("date", "").strip()
    if not date_param:
        return jsonify({"error": "Missing 'date' parameter in YYYY-MM-DD format."}), 400

    try:
        parsed_date = datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

    today = date.today()
    is_past = parsed_date < today

    slot_info = get_available_slots_for_date(date_param)

    # If date is in the past, no slots are available to book
    if is_past:
        return jsonify({
            "date": date_param,
            "is_past": True,
            "all_slots": WORKING_TIME_SLOTS,
            "available_slots": [],
            "booked_slots": slot_info["booked_slots"],
            "message": "Selected date is in the past. No booking slots available."
        }), 200

    return jsonify({
        "date": date_param,
        "is_past": False,
        "all_slots": WORKING_TIME_SLOTS,
        "available_slots": slot_info["available_slots"],
        "booked_slots": slot_info["booked_slots"],
        "message": f"{len(slot_info['available_slots'])} of {len(WORKING_TIME_SLOTS)} slots available."
    }), 200


@app.route("/appointments", methods=["GET"])
def appointments():
    """
    View Appointments page.
    Allows searching by email, filtering by date and booking status.
    Returns HTML template or JSON if requested.
    """
    search_email = request.args.get("email", "").strip()
    filter_date = request.args.get("date", "").strip()
    filter_status = request.args.get("status", "All").strip()
    highlight_id = request.args.get("new_id", type=int)
    cancellation_token = request.args.get("token", "").strip()

    appointment_list = get_appointments(
        email=search_email if search_email else None,
        appointment_date=filter_date if filter_date else None,
        status=filter_status if filter_status != "All" else None
    )

    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "appointments": appointment_list,
            "count": len(appointment_list)
        })

    return render_template(
        "appointments.html",
        appointments=appointment_list,
        search_email=search_email,
        filter_date=filter_date,
        filter_status=filter_status,
        highlight_id=highlight_id,
        cancellation_token=cancellation_token
    )


@app.route("/cancel/<int:appointment_id>", methods=["POST"])
def cancel(appointment_id: int):
    """
    Cancel an appointment securely.
    Accepts cancellation token via JSON body, form body, or Authorization / query string.
    """
    token = None
    if request.is_json:
        data = request.get_json() or {}
        token = data.get("cancellation_token") or data.get("token")
    elif request.form:
        token = request.form.get("cancellation_token") or request.form.get("token")

    if not token:
        token = request.args.get("token")

    if not token:
        msg = "Cancellation token is missing. Please provide the token received during booking."
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("appointments"))

    success, message = cancel_appointment(appointment_id, token)

    if not success:
        status_code = 400
        if "not found" in message.lower():
            status_code = 404
        elif "unauthorized" in message.lower() or "invalid" in message.lower():
            status_code = 403

        if request.is_json:
            return jsonify({"success": False, "error": message}), status_code
        flash(message, "danger")
        return redirect(url_for("appointments"))

    if request.is_json:
        return jsonify({"success": True, "message": message}), 200

    flash(message, "success")
    return redirect(url_for("appointments"))


@app.route("/contact")
def contact():
    """Contact & support information page."""
    return render_template("contact.html")


@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.path.startswith("/available-slots"):
        return jsonify({"error": "Resource not found"}), 404
    return render_template("base.html", error_title="404 - Page Not Found",
                           error_msg="The requested page could not be located."), 404


@app.errorhandler(500)
def server_error(e):
    if request.is_json:
        return jsonify({"error": "Internal server error"}), 500
    return render_template("base.html", error_title="500 - Server Error",
                           error_msg="An unexpected error occurred. Please try again later."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Appointment Booking System running on http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
