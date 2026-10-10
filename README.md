# AppointFlow — Appointment Booking System

A complete, modern, responsive web application for managing appointments. Built with **Python (Flask)**, **SQLite**, and vanilla **HTML5/CSS3/JavaScript**.

AppointFlow provides seamless scheduling within business hours (9:00 AM – 5:00 PM), dynamic slot availability checks, duplicate booking prevention via database constraints and atomic transactions, appointment search/filtering by email, and secure token-verified cancellations.

---

## 🌟 Key Features

1. **Conflict-Free Scheduling (Duplicate Booking Prevention)**:
   - Enforces a SQLite database-level **Partial Unique Index** (`idx_unique_active_booking`) on `(appointment_date, time_slot)` where `status = 'Booked'`.
   - Uses atomic transactions with `BEGIN IMMEDIATE` to prevent race conditions during simultaneous bookings.
   - If two users request the same slot at the exact same millisecond, only the first request succeeds; the second receives a clear notification: *"This time slot is already booked. Please select another time."*
2. **Dynamic Slot Availability**:
   - Time slots are retrieved dynamically from the backend for the selected date.
   - Past calendar dates cannot be selected or booked.
   - Predefined working hours (9:00 AM to 5:00 PM) with 1-hour slots.
3. **Secure Token-Based Cancellation**:
   - Each booking generates a high-entropy 32-byte cryptographic cancellation token (`secrets.token_urlsafe(32)`).
   - Only a cryptographic hash (`SHA-256`) is stored in the database.
   - Users can cancel their appointment securely by supplying the token.
   - When an appointment is cancelled, its status is updated to `"Cancelled"` (audit history preserved), and the time slot **instantly becomes available again** for new bookings.
4. **My Appointments Management**:
   - Search and look up bookings using your email address.
   - Filter records by date and status (*All*, *Booked*, *Cancelled*).
   - Responsive cards and desktop view with visual badges and easy one-click cancellation.
5. **Modern, Responsive UI/UX**:
   - Light background theme with vibrant indigo/purple accents.
   - Fully responsive for mobile devices, tablets, and desktop displays.
   - Real-time client-side and server-side validation with inline error feedback.
   - Copy-to-clipboard functionality for cancellation tokens.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | HTML5, Modern CSS3 (Flexbox, CSS Grid, Glassmorphism), Vanilla JavaScript (ES6+) |
| **Backend** | Python 3, Flask |
| **Database** | SQLite (with WAL mode, parameterized queries, partial unique index) |
| **Testing** | Pytest |

---

## 📂 Project Structure

```text
appointment-booking-system/
├── app.py                     # Main Flask web application and routing
├── database.py                # Database connection, schemas, transactions, queries
├── requirements.txt           # Project dependencies
├── README.md                  # Documentation and setup guide
├── appointments.db            # SQLite database (auto-generated on launch)
├── templates/
│   ├── base.html              # Base HTML template with navbar and notifications
│   ├── index.html             # Home page with hero, live metrics, and features
│   ├── book.html              # Interactive booking form with dynamic slot grid
│   ├── appointments.html      # Appointments listing, email search, and cancellation modal
│   └── contact.html           # Contact information, working hours, and FAQs
├── static/
│   ├── css/
│   │   └── style.css          # Responsive design, custom components, and color themes
│   └── js/
│       └── script.js          # Client-side validation, AJAX slot fetching, modals
└── tests/
    ├── __init__.py
    └── test_app.py            # Automated pytest suite covering all 10 scenarios
```

---

## 🚀 Installation & Execution

### 1. Prerequisites
- Python 3.10+ installed.

### 2. Install Dependencies
Navigate to the project root directory and install dependencies:
```bash
cd appointment-booking-system
pip install -r requirements.txt
```

### 3. Run the Application
Start the Flask application server:
```bash
python app.py
```

The application will start on:
```text
http://127.0.0.1:5001
```
*(Port can be customized by setting the `PORT` environment variable, e.g., `PORT=5000 python app.py`)*.

---

## 🧪 Running Automated Tests

Run the test suite covering all 10 core scenarios:
```bash
python -m pytest tests/test_app.py -v
```

### Tested Scenarios:
1. `test_scenario_1_successful_booking` — Successfully books an available appointment.
2. `test_scenario_2_invalid_or_missing_inputs_rejected` — Validates required fields, email format, phone format, and reason length.
3. `test_scenario_3_past_dates_cannot_be_booked` — Disallows selecting or submitting past dates.
4. `test_scenario_4_duplicate_bookings_rejected` — Rejects second booking attempt on identical date and slot.
5. `test_scenario_5_different_time_slots_same_date` — Allows booking different slots on the same date.
6. `test_scenario_6_users_can_view_appointments` — Verifies appointments listing and email lookup.
7. `test_scenario_7_users_can_cancel_own_appointments_securely` — Cancels booking with valid security token.
8. `test_scenario_8_cancelled_slots_become_available_again` — Verifies cancelled slots reopen immediately for booking.
9. `test_scenario_9_invalid_id_and_unauthorized_cancellation_handled_safely` — Blocks wrong tokens and fake IDs.
10. `test_scenario_10_database_errors_and_edge_cases_handled_gracefully` — Validates slot boundaries and date parsing.

---

## 🔍 How to Test Each Feature in the Browser

1. **Book an Appointment**:
   - Go to `http://127.0.0.1:5001/book`.
   - Select today's date or a future date. Notice how the time slot chips update with availability.
   - Choose a slot (e.g. `10:00 AM - 11:00 AM`).
   - Enter your name, email, phone, and reason.
   - Click **Confirm & Book Appointment**.
   - A success popup will appear showing your **Appointment ID** and your **Cancellation Token**. Click **Copy** to save your token!

2. **Test Duplicate Booking Prevention**:
   - Try booking the exact same date and time slot that you just booked.
   - You will see the slot is marked as **Booked** in the UI. If you attempt to force submission, the system displays:
     > *"This time slot is already booked. Please select another time."*

3. **View Appointments**:
   - Go to `http://127.0.0.1:5001/appointments`.
   - Enter your email address in the **Lookup by Email** input and click **Filter**.
   - You will see your booked appointment displayed with date, time, reason, and an active **Booked** badge.

4. **Cancel an Appointment**:
   - On the appointment card, click **Cancel Booking**.
   - A confirmation modal will appear. Paste your cancellation token and click **Confirm Cancellation**.
   - The card status immediately updates to **Cancelled** with a *"Slot released"* notice.

5. **Verify Re-opened Slot**:
   - Go back to `http://127.0.0.1:5001/book` and pick that same date.
   - The slot you just cancelled is now **Available** and can be booked by anyone again!

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Home dashboard page with live metrics |
| `GET` | `/book` | Render booking form |
| `POST` | `/book` | Submit new appointment booking (JSON or Form POST) |
| `GET` | `/available-slots?date=YYYY-MM-DD` | Returns JSON of available and booked slots |
| `GET` | `/appointments` | View or search appointments (HTML or JSON) |
| `POST` | `/cancel/<id>` | Cancel an appointment with cancellation token |
| `GET` | `/contact` | Contact, support hours, and FAQ page |

---

## 🔒 Security Highlights

- **SQL Injection Prevention**: 100% parameterized SQLite queries.
- **Cryptographic Tokens**: Raw cancellation tokens are never stored in plaintext; only salted SHA-256 hashes are persisted. Token comparison is performed using constant-time `secrets.compare_digest`.
- **Double-Booking Race Condition Prevention**: SQLite `BEGIN IMMEDIATE` transaction locking combined with unique partial index constraints.
- **Input Sanitization & Server-side Validation**: Strict regex rules and length limits on all client inputs.
