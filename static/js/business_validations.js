/**
 * Business validation utilities for the Gestion-Personnel-DU-CVB application.
 *
 * This module provides client-side validation that mirrors the server-side
 * validations in apps/common/business_validators.py.
 *
 * Validations:
 * - Date range validation (start_date must be <= end_date)
 * - Time range validation (start_time must be < end_time)
 * - Working hours validation (08:00-17:00, lunch break excluded)
 * - Weekend exclusion awareness
 *
 * Usage:
 *   BusinessValidations.init();  // Auto-initializes all form validations
 *
 *   // Or use individual methods:
 *   BusinessValidations.validateDateRange(startDate, endDate);
 *   BusinessValidations.validateTimeRange(startTime, endTime);
 *   BusinessValidations.validateWorkingHours(startTime, endTime);
 */

(function () {
    "use strict";

    // Working hours constants (must match server-side)
    var WORK_START_MORNING = 8 * 60;    // 08:00
    var WORK_END_MORNING = 12 * 60;     // 12:00
    var WORK_START_AFTERNOON = 13 * 60; // 13:00
    var WORK_END_AFTERNOON = 17 * 60;   // 17:00

    /**
     * Convert a time string "HH:MM" or Date object to minutes since midnight.
     */
    function timeToMinutes(timeValue) {
        if (!timeValue) return null;
        var parts = String(timeValue).split(":");
        var hours = parseInt(parts[0], 10);
        var minutes = parseInt(parts[1], 10);
        if (isNaN(hours) || isNaN(minutes)) return null;
        return hours * 60 + minutes;
    }

    /**
     * Parse a date string "YYYY-MM-DD" to a Date object.
     */
    function parseDate(dateString) {
        if (!dateString) return null;
        var parts = String(dateString).split("-");
        if (parts.length !== 3) return null;
        var year = parseInt(parts[0], 10);
        var month = parseInt(parts[1], 10);
        var day = parseInt(parts[2], 10);
        if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
        return new Date(year, month - 1, day);
    }

    /**
     * Check if a date is a weekend (Saturday or Sunday).
     */
    function isWeekend(date) {
        if (!date) return false;
        var day = date.getDay();
        return day === 0 || day === 6; // Sunday=0, Saturday=6
    }

    var BusinessValidations = {
        /**
         * Validate that start_date is not after end_date.
         * @param {string} startDateStr - "YYYY-MM-DD"
         * @param {string} endDateStr - "YYYY-MM-DD"
         * @returns {{valid: boolean, message: string}}
         */
        validateDateRange: function (startDateStr, endDateStr) {
            var start = parseDate(startDateStr);
            var end = parseDate(endDateStr);
            if (!start || !end) {
                return { valid: true, message: "" };
            }
            if (end < start) {
                return {
                    valid: false,
                    message: "La date de fin doit etre apres ou egale a la date de debut.",
                };
            }
            return { valid: true, message: "" };
        },

        /**
         * Validate that start_time is before end_time.
         * @param {string} startTimeStr - "HH:MM"
         * @param {string} endTimeStr - "HH:MM"
         * @returns {{valid: boolean, message: string}}
         */
        validateTimeRange: function (startTimeStr, endTimeStr) {
            var startMin = timeToMinutes(startTimeStr);
            var endMin = timeToMinutes(endTimeStr);
            if (startMin === null || endMin === null) {
                return { valid: true, message: "" };
            }
            if (endMin <= startMin) {
                return {
                    valid: false,
                    message: "L'heure de fin doit etre apres l'heure de debut.",
                };
            }
            return { valid: true, message: "" };
        },

        /**
         * Validate that the time range falls within working hours (08:00-17:00).
         * @param {string} startTimeStr - "HH:MM"
         * @param {string} endTimeStr - "HH:MM"
         * @returns {{valid: boolean, message: string}}
         */
        validateWorkingHours: function (startTimeStr, endTimeStr) {
            var startMin = timeToMinutes(startTimeStr);
            var endMin = timeToMinutes(endTimeStr);
            if (startMin === null || endMin === null) {
                return { valid: true, message: "" };
            }

            if (startMin < WORK_START_MORNING) {
                return {
                    valid: false,
                    message: "L'heure de debut ne peut pas etre avant 08:00.",
                };
            }

            if (endMin > WORK_END_AFTERNOON) {
                return {
                    valid: false,
                    message: "L'heure de fin ne peut pas etre apres 17:00.",
                };
            }

            // Check if the range covers any working time
            var morningOverlap = Math.max(0, Math.min(endMin, WORK_END_MORNING) - Math.max(startMin, WORK_START_MORNING));
            var afternoonOverlap = Math.max(0, Math.min(endMin, WORK_END_AFTERNOON) - Math.max(startMin, WORK_START_AFTERNOON));
            var totalWorkingMinutes = morningOverlap + afternoonOverlap;

            if (totalWorkingMinutes <= 0) {
                return {
                    valid: false,
                    message: "La plage horaire choisie ne couvre aucun temps de travail.",
                };
            }

            return { valid: true, message: "" };
        },

        /**
         * Check if a date is a weekend.
         * @param {string} dateStr - "YYYY-MM-DD"
         * @returns {boolean}
         */
        isWeekend: function (dateStr) {
            return isWeekend(parseDate(dateStr));
        },

        /**
         * Show an inline error message next to a field.
         * @param {HTMLElement} field - The input field
         * @param {string} message - Error message to display
         */
        showFieldError: function (field, message) {
            if (!field) return;
            field.classList.add("is-invalid");
            field.setAttribute("aria-invalid", "true");

            // Remove existing error message
            var existing = field.parentNode.querySelector(".invalid-feedback");
            if (existing) {
                existing.remove();
            }

            if (message) {
                var feedback = document.createElement("div");
                feedback.className = "invalid-feedback";
                feedback.textContent = message;
                field.parentNode.appendChild(feedback);
            }
        },

        /**
         * Clear inline error message from a field.
         * @param {HTMLElement} field - The input field
         */
        clearFieldError: function (field) {
            if (!field) return;
            field.classList.remove("is-invalid");
            field.setAttribute("aria-invalid", "false");
            var existing = field.parentNode.querySelector(".invalid-feedback");
            if (existing) {
                existing.remove();
            }
        },

        /**
         * Initialize all form validations on the page.
         * This auto-binds to forms with data attributes for date/time validation.
         */
        init: function () {
            var self = this;

            // Date range validation: forms with data-date-range-validate
            var dateRangeForms = document.querySelectorAll("[data-date-range-validate]");
            dateRangeForms.forEach(function (form) {
                var startDateField = form.querySelector("[data-start-date], [name='start_date'], #id_start_date");
                var endDateField = form.querySelector("[data-end-date], [name='end_date'], #id_end_date");

                if (startDateField && endDateField) {
                    var validate = function () {
                        self.clearFieldError(endDateField);
                        var result = self.validateDateRange(startDateField.value, endDateField.value);
                        if (!result.valid) {
                            self.showFieldError(endDateField, result.message);
                        }
                    };

                    startDateField.addEventListener("change", validate);
                    endDateField.addEventListener("change", validate);
                }
            });

            // Time range validation: forms with data-time-range-validate
            var timeRangeForms = document.querySelectorAll("[data-time-range-validate]");
            timeRangeForms.forEach(function (form) {
                var startTimeField = form.querySelector("[data-start-time], [name='start_time'], #id_start_time");
                var endTimeField = form.querySelector("[data-end-time], [name='end_time'], #id_end_time");

                if (startTimeField && endTimeField) {
                    var validate = function () {
                        self.clearFieldError(endTimeField);
                        self.clearFieldError(startTimeField);

                        var timeResult = self.validateTimeRange(startTimeField.value, endTimeField.value);
                        if (!timeResult.valid) {
                            self.showFieldError(endTimeField, timeResult.message);
                        }

                        var hoursResult = self.validateWorkingHours(startTimeField.value, endTimeField.value);
                        if (!hoursResult.valid) {
                            self.showFieldError(startTimeField, hoursResult.message);
                        }
                    };

                    startTimeField.addEventListener("change", validate);
                    endTimeField.addEventListener("change", validate);
                }
            });

            // Recovery line time validation: forms with data-recovery-line-validate
            var recoveryForms = document.querySelectorAll("[data-recovery-line-validate]");
            recoveryForms.forEach(function (form) {
                var startTimeField = form.querySelector("[data-start-time], [name='start_time'], #id_start_time");
                var endTimeField = form.querySelector("[data-end-time], [name='end_time'], #id_end_time");

                if (startTimeField && endTimeField) {
                    var validate = function () {
                        self.clearFieldError(endTimeField);
                        self.clearFieldError(startTimeField);

                        var timeResult = self.validateTimeRange(startTimeField.value, endTimeField.value);
                        if (!timeResult.valid) {
                            self.showFieldError(endTimeField, timeResult.message);
                        }

                        var hoursResult = self.validateWorkingHours(startTimeField.value, endTimeField.value);
                        if (!hoursResult.valid) {
                            self.showFieldError(startTimeField, hoursResult.message);
                        }
                    };

                    startTimeField.addEventListener("change", validate);
                    endTimeField.addEventListener("change", validate);
                }
            });

            // Prevent form submission if there are validation errors
            var allValidatedForms = document.querySelectorAll("[data-date-range-validate], [data-time-range-validate], [data-recovery-line-validate]");
            allValidatedForms.forEach(function (form) {
                form.addEventListener("submit", function (e) {
                    var invalidFields = form.querySelectorAll(".is-invalid");
                    if (invalidFields.length > 0) {
                        e.preventDefault();
                        invalidFields[0].focus();
                    }
                });
            });
        },
    };

    // Expose globally
    window.BusinessValidations = BusinessValidations;

    // Auto-initialize on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            BusinessValidations.init();
        });
    } else {
        BusinessValidations.init();
    }
})();
