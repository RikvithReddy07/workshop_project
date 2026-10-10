/**
 * AppointFlow - Frontend JavaScript
 * Handles:
 * - Responsive navigation
 * - Dynamic slot checking via API
 * - Real-time form validation
 * - Conflict / duplicate booking feedback
 * - Success & cancellation modals
 * - Clipboard copy for security token
 */

document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initBookingForm();
    initAppointmentsPage();
});

/* ==========================================================================
   Navigation
   ========================================================================== */
function initNavigation() {
    const navToggle = document.getElementById("navToggle");
    const navLinks = document.getElementById("navLinks");

    if (navToggle && navLinks) {
        navToggle.addEventListener("click", () => {
            const isOpen = navLinks.classList.toggle("open");
            navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        // Close mobile nav when clicking outside
        document.addEventListener("click", (e) => {
            if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove("open");
                navToggle.setAttribute("aria-expanded", "false");
            }
        });
    }
}

/* ==========================================================================
   Booking Page Logic
   ========================================================================== */
function initBookingForm() {
    const form = document.getElementById("bookingForm");
    if (!form) return;

    const dateInput = document.getElementById("appointment_date");
    const timeSlotInput = document.getElementById("time_slot");
    const slotSummary = document.getElementById("slotSummaryDisplay");
    const slotsGrid = document.getElementById("timeSlotsGrid");
    const slotsLoader = document.getElementById("slotsLoader");
    const slotsDateDisplay = document.getElementById("slotsDateDisplay");
    const formAlert = document.getElementById("formAlert");
    const formAlertMessages = document.getElementById("formAlertMessages");
    const submitBtn = document.getElementById("submitBtn");
    const reasonTextarea = document.getElementById("reason");
    const reasonCharCount = document.getElementById("reasonCharCount");

    // Enforce min date to today's local date
    const today = new Date().toISOString().split("T")[0];
    if (dateInput) {
        dateInput.min = today;
        if (!dateInput.value) {
            dateInput.value = today;
        }

        // Fetch slots when date changes
        dateInput.addEventListener("change", () => {
            clearFieldError("appointment_date");
            fetchAvailableSlots(dateInput.value);
        });

        // Initial fetch on page load
        fetchAvailableSlots(dateInput.value);
    }

    // Reason character count listener
    if (reasonTextarea && reasonCharCount) {
        reasonCharCount.textContent = reasonTextarea.value.length;
        reasonTextarea.addEventListener("input", () => {
            reasonCharCount.textContent = reasonTextarea.value.length;
            if (reasonTextarea.value.trim().length >= 3) {
                clearFieldError("reason");
            }
        });
    }

    // Attach real-time input listeners for validation
    ["full_name", "email", "phone"].forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (input) {
            input.addEventListener("input", () => {
                validateField(fieldId);
            });
            input.addEventListener("blur", () => {
                validateField(fieldId);
            });
        }
    });

    /**
     * Fetch available slots for date
     */
    async function fetchAvailableSlots(dateStr) {
        if (!dateStr) return;

        if (slotsDateDisplay) {
            slotsDateDisplay.textContent = dateStr;
        }

        if (slotsLoader) slotsLoader.style.display = "flex";

        try {
            const response = await fetch(`/available-slots?date=${encodeURIComponent(dateStr)}`);
            const data = await response.json();

            if (!response.ok) {
                showFormAlert([data.error || "Failed to load slots for this date."]);
                return;
            }

            if (data.is_past) {
                renderPastDateState(slotsGrid);
                timeSlotInput.value = "";
                updateSlotSummaryDisplay("");
                return;
            }

            renderSlots(data.all_slots, data.available_slots, data.booked_slots);

        } catch (err) {
            console.error("Slot fetch error:", err);
            showFormAlert(["Network error while loading available time slots. Please refresh."]);
        } finally {
            if (slotsLoader) slotsLoader.style.display = "none";
        }
    }

    /**
     * Render slot buttons with Available / Booked states
     */
    function renderSlots(allSlots, availableSlots, bookedSlots) {
        if (!slotsGrid) return;
        slotsGrid.innerHTML = "";

        const currentSelected = timeSlotInput.value;
        const availableSet = new Set(availableSlots);
        const bookedSet = new Set(bookedSlots);

        // If currently selected slot is now booked or invalid on new date, reset it
        if (currentSelected && !availableSet.has(currentSelected)) {
            timeSlotInput.value = "";
            updateSlotSummaryDisplay("");
        }

        allSlots.forEach(slot => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "slot-btn";
            btn.setAttribute("role", "radio");
            btn.dataset.slot = slot;

            const isBooked = bookedSet.has(slot);
            const isSelected = slot === timeSlotInput.value;

            if (isBooked) {
                btn.classList.add("booked");
                btn.disabled = true;
                btn.title = "This time slot is already booked";
                btn.setAttribute("aria-disabled", "true");
                btn.setAttribute("aria-checked", "false");
            } else {
                btn.setAttribute("aria-checked", isSelected ? "true" : "false");
            }

            if (isSelected) {
                btn.classList.add("selected");
            }

            btn.innerHTML = `
                <span class="slot-clock-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12 6 12 12 16 14"></polyline>
                    </svg>
                </span>
                <span class="slot-text">${slot}</span>
            `;

            btn.addEventListener("click", () => {
                if (btn.disabled || btn.classList.contains("booked")) return;

                // Deselect other buttons
                slotsGrid.querySelectorAll(".slot-btn").forEach(b => {
                    b.classList.remove("selected");
                    b.setAttribute("aria-checked", "false");
                });

                // Select this button
                btn.classList.add("selected");
                btn.setAttribute("aria-checked", "true");
                timeSlotInput.value = slot;
                updateSlotSummaryDisplay(slot);
                clearFieldError("time_slot");
            });

            slotsGrid.appendChild(btn);
        });

        // Update display with current slot if valid
        if (timeSlotInput.value && availableSet.has(timeSlotInput.value)) {
            updateSlotSummaryDisplay(timeSlotInput.value);
        }
    }

    function renderPastDateState(container) {
        if (!container) return;
        container.innerHTML = `
            <div style="grid-column: 1 / -1; padding: 1.5rem; text-align: center; color: var(--danger); background: var(--danger-bg); border-radius: var(--radius-md); border: 1px solid var(--danger-border);">
                <strong>Past Date Selected:</strong> Booking slots are only available for today and future business days.
            </div>
        `;
    }

    function updateSlotSummaryDisplay(slot) {
        if (!slotSummary) return;
        if (slot) {
            slotSummary.classList.remove("empty");
            slotSummary.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px;">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>${slot}</span>
            `;
        } else {
            slotSummary.classList.add("empty");
            slotSummary.innerHTML = `<span class="slot-preview-text">Please pick a slot below</span>`;
        }
    }

    /**
     * Submit handler: AJAX booking with instant UI feedback
     */
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideFormAlert();

        const isValid = validateEntireForm();
        if (!isValid) {
            // Scroll to first invalid field
            const firstError = form.querySelector(".is-invalid, .field-error.active");
            if (firstError) {
                firstError.scrollIntoView({ behavior: "smooth", block: "center" });
            }
            return;
        }

        // Prepare JSON payload
        const payload = {
            full_name: document.getElementById("full_name").value.trim(),
            email: document.getElementById("email").value.trim(),
            phone: document.getElementById("phone").value.trim(),
            appointment_date: dateInput.value,
            time_slot: timeSlotInput.value,
            reason: reasonTextarea.value.trim()
        };

        setButtonLoading(submitBtn, true);

        try {
            const response = await fetch("/book", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.status === 201 && result.success) {
                // Success! Open confirmation modal with token
                openSuccessModal(result.appointment);
                // Reset form
                form.reset();
                dateInput.value = today;
                timeSlotInput.value = "";
                updateSlotSummaryDisplay("");
                if (reasonCharCount) reasonCharCount.textContent = "0";
                // Refresh slots
                fetchAvailableSlots(today);

            } else if (response.status === 409) {
                // Slot conflict / duplicate
                showFormAlert([
                    result.errors ? result.errors.join(" ") : "This time slot is already booked. Please select another time."
                ]);
                // Refresh slots immediately to show it as booked
                fetchAvailableSlots(dateInput.value);

            } else {
                // Validation or server error
                const errorList = result.errors || [result.message || "An error occurred while booking. Please try again."];
                showFormAlert(errorList);
            }

        } catch (err) {
            console.error("Booking submission error:", err);
            showFormAlert(["An unexpected network error occurred. Please check your connection and try again."]);
        } finally {
            setButtonLoading(submitBtn, false);
        }
    });

    /**
     * Form validation helpers
     */
    function validateField(fieldId) {
        const input = document.getElementById(fieldId);
        if (!input) return true;

        const val = input.value.trim();

        if (fieldId === "full_name") {
            if (val.length < 2) {
                setFieldError("full_name", "Full Name is required (minimum 2 characters).");
                return false;
            }
            clearFieldError("full_name");
            return true;
        }

        if (fieldId === "email") {
            const emailRegex = /^[\w\.-]+@[\w\.-]+\.\w{2,}$/;
            if (!val || !emailRegex.test(val)) {
                setFieldError("email", "Please provide a valid email address (e.g. name@example.com).");
                return false;
            }
            clearFieldError("email");
            return true;
        }

        if (fieldId === "phone") {
            const phoneDigits = val.replace(/\D/g, "");
            if (phoneDigits.length < 7 || phoneDigits.length > 15) {
                setFieldError("phone", "Please provide a valid phone number (7 to 15 digits).");
                return false;
            }
            clearFieldError("phone");
            return true;
        }

        return true;
    }

    function validateEntireForm() {
        let valid = true;

        if (!validateField("full_name")) valid = false;
        if (!validateField("email")) valid = false;
        if (!validateField("phone")) valid = false;

        // Validate date
        if (!dateInput.value) {
            setFieldError("appointment_date", "Appointment Date is required.");
            valid = false;
        } else if (dateInput.value < today) {
            setFieldError("appointment_date", "Appointment Date cannot be in the past.");
            valid = false;
        } else {
            clearFieldError("appointment_date");
        }

        // Validate time slot
        if (!timeSlotInput.value) {
            setFieldError("time_slot", "Please select an available time slot from the options below.");
            valid = false;
        } else {
            clearFieldError("time_slot");
        }

        // Validate reason
        if (!reasonTextarea.value.trim() || reasonTextarea.value.trim().length < 3) {
            setFieldError("reason", "Please provide a reason for the appointment (minimum 3 characters).");
            valid = false;
        } else {
            clearFieldError("reason");
        }

        return valid;
    }

    function setFieldError(fieldId, errorMsg) {
        const input = document.getElementById(fieldId);
        let errorSpanId = fieldId + "Error";
        if (fieldId === "appointment_date") errorSpanId = "dateError";
        if (fieldId === "time_slot") errorSpanId = "slotError";

        const errorSpan = document.getElementById(errorSpanId);
        if (input && input.tagName !== "INPUT" && input.type === "hidden") {
            // hidden input
        } else if (input) {
            input.classList.add("is-invalid");
        }
        if (errorSpan) {
            errorSpan.textContent = errorMsg;
            errorSpan.classList.add("active");
        }
    }

    function clearFieldError(fieldId) {
        const input = document.getElementById(fieldId);
        let errorSpanId = fieldId + "Error";
        if (fieldId === "appointment_date") errorSpanId = "dateError";
        if (fieldId === "time_slot") errorSpanId = "slotError";

        const errorSpan = document.getElementById(errorSpanId);
        if (input) input.classList.remove("is-invalid");
        if (errorSpan) {
            errorSpan.textContent = "";
            errorSpan.classList.remove("active");
        }
    }

    function showFormAlert(messages) {
        if (!formAlert || !formAlertMessages) return;
        formAlertMessages.innerHTML = messages.map(m => `<div>${escapeHtml(m)}</div>`).join("");
        formAlert.style.display = "flex";
        formAlert.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function hideFormAlert() {
        if (formAlert) formAlert.style.display = "none";
    }
}

/* ==========================================================================
   Success Modal Handling
   ========================================================================== */
function openSuccessModal(appt) {
    const modal = document.getElementById("successModal");
    if (!modal) return;

    document.getElementById("summaryId").textContent = `#${appt.id}`;
    document.getElementById("summaryName").textContent = appt.full_name;
    document.getElementById("summaryDateTime").textContent = `${appt.appointment_date} at ${appt.time_slot}`;
    document.getElementById("summaryEmail").textContent = appt.email;
    document.getElementById("summaryToken").value = appt.cancellation_token;

    // View Appointment button link
    const viewBtn = document.getElementById("viewAppointmentBtn");
    if (viewBtn) {
        viewBtn.href = `/appointments?email=${encodeURIComponent(appt.email)}&new_id=${appt.id}&token=${encodeURIComponent(appt.cancellation_token)}`;
    }

    // Copy Token setup
    const copyBtn = document.getElementById("copyTokenBtn");
    const copyLabel = document.getElementById("copyBtnLabel");
    if (copyBtn) {
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(appt.cancellation_token).then(() => {
                copyLabel.textContent = "Copied!";
                setTimeout(() => { copyLabel.textContent = "Copy"; }, 2500);
            }).catch(() => {
                // Fallback select
                document.getElementById("summaryToken").select();
                copyLabel.textContent = "Copied!";
            });
        };
    }

    modal.style.display = "flex";
}

function closeSuccessModal() {
    const modal = document.getElementById("successModal");
    if (modal) modal.style.display = "none";
}

/* ==========================================================================
   Appointments Page & Cancellation Modal
   ========================================================================== */
function initAppointmentsPage() {
    const cancelModal = document.getElementById("cancelModal");
    const cancelForm = document.getElementById("cancelForm");
    const cancelTokenInput = document.getElementById("cancelTokenInput");
    const cancelTokenError = document.getElementById("cancelTokenError");
    const confirmCancelBtn = document.getElementById("confirmCancelBtn");

    let activeAppointmentId = null;

    // Attach click listeners to all Cancel buttons
    document.querySelectorAll(".cancel-trigger-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const id = btn.dataset.id;
            const name = btn.dataset.name;
            const date = btn.dataset.date;
            const time = btn.dataset.time;
            const token = btn.dataset.token;

            activeAppointmentId = id;

            document.getElementById("cancelModalApptId").textContent = `#${id}`;
            document.getElementById("cancelModalName").textContent = name;
            document.getElementById("cancelModalSchedule").textContent = `${date} &bull; ${time}`;

            if (cancelTokenInput) {
                cancelTokenInput.value = token || "";
                cancelTokenInput.classList.remove("is-invalid");
            }
            if (cancelTokenError) {
                cancelTokenError.textContent = "";
                cancelTokenError.classList.remove("active");
            }

            if (cancelForm) {
                cancelForm.action = `/cancel/${id}`;
            }

            if (cancelModal) {
                cancelModal.style.display = "flex";
            }
        });
    });

    // Handle Cancel Form submission via AJAX for instant reactivity
    if (cancelForm) {
        cancelForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const tokenVal = cancelTokenInput.value.trim();
            if (!tokenVal) {
                cancelTokenInput.classList.add("is-invalid");
                if (cancelTokenError) {
                    cancelTokenError.textContent = "Cancellation token is required.";
                    cancelTokenError.classList.add("active");
                }
                return;
            }

            setButtonLoading(confirmCancelBtn, true);

            try {
                const response = await fetch(`/cancel/${activeAppointmentId}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    body: JSON.stringify({ cancellation_token: tokenVal })
                });

                const result = await response.json();

                if (response.ok && result.success) {
                    closeCancelModal();
                    // Update appointment card in UI immediately
                    const card = document.getElementById(`appt-card-${activeAppointmentId}`);
                    if (card) {
                        card.classList.add("cancelled-card");
                        const statusBadge = card.querySelector(".appt-status");
                        if (statusBadge) {
                            statusBadge.innerHTML = `<span class="badge badge-neutral"><span class="status-dot-cancelled"></span> Cancelled</span>`;
                        }
                        const footer = card.querySelector(".appt-card-footer");
                        if (footer) {
                            const btn = footer.querySelector(".cancel-trigger-btn");
                            if (btn) btn.remove();
                            const span = document.createElement("span");
                            span.className = "text-muted-small";
                            span.textContent = "Slot released";
                            footer.appendChild(span);
                        }
                    }
                    showToast("Appointment cancelled successfully. The slot is now reopened.", "success");
                } else {
                    cancelTokenInput.classList.add("is-invalid");
                    if (cancelTokenError) {
                        cancelTokenError.textContent = result.error || "Failed to cancel appointment.";
                        cancelTokenError.classList.add("active");
                    }
                }

            } catch (err) {
                console.error("Cancellation error:", err);
                if (cancelTokenError) {
                    cancelTokenError.textContent = "A network error occurred. Please try again.";
                    cancelTokenError.classList.add("active");
                }
            } finally {
                setButtonLoading(confirmCancelBtn, false);
            }
        });
    }
}

function closeCancelModal() {
    const modal = document.getElementById("cancelModal");
    if (modal) modal.style.display = "none";
}

/* ==========================================================================
   Utilities
   ========================================================================== */
function setButtonLoading(btn, isLoading) {
    if (!btn) return;
    const textSpan = btn.querySelector(".btn-text");
    const spinnerSpan = btn.querySelector(".btn-spinner");

    if (isLoading) {
        btn.disabled = true;
        if (textSpan) textSpan.style.display = "none";
        if (spinnerSpan) spinnerSpan.style.display = "inline-flex";
    } else {
        btn.disabled = false;
        if (textSpan) textSpan.style.display = "inline";
        if (spinnerSpan) spinnerSpan.style.display = "none";
    }
}

function showToast(message, type = "success") {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        container.className = "toast-container container";
        document.body.insertBefore(container, document.querySelector("main"));
    }

    const alert = document.createElement("div");
    alert.className = `alert alert-${type} alert-dismissible`;
    alert.setAttribute("role", "alert");
    alert.innerHTML = `
        <div class="alert-content">
            <span class="alert-icon">
                ${type === 'success' ? 
                  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>' : 
                  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'}
            </span>
            <span class="alert-text">${escapeHtml(message)}</span>
        </div>
        <button type="button" class="btn-close" aria-label="Close" onclick="this.closest('.alert').remove()">&times;</button>
    `;

    container.appendChild(alert);
    setTimeout(() => {
        alert.remove();
    }, 6000);
}

function escapeHtml(text) {
    if (!text) return "";
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
