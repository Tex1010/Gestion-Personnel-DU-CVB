"""
Business validation utilities for the Gestion-Personnel-DU-CVB application.

This module centralizes all business-rule validations to avoid duplication
between the interface (JavaScript) and the server (Django).

Validations provided:
- Date range validation (start_date must be <= end_date)
- Overlap detection for staff requests and HR events
- Weekend exclusion (Saturday/Sunday) for day-counting
- Time range validation (start_time must be < end_time, within working hours)
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

# Working hours constants (used for time validation)
WORK_START_MORNING = 8 * 60    # 08:00 in minutes
WORK_END_MORNING = 12 * 60     # 12:00 in minutes
WORK_START_AFTERNOON = 13 * 60  # 13:00 in minutes
WORK_END_AFTERNOON = 17 * 60    # 17:00 in minutes
FULL_DAY_MINUTES = 8 * 60       # 8 hours = 480 minutes


def time_to_minutes(time_value):
    """Convert a datetime.time or 'HH:MM' string to minutes since midnight."""
    if hasattr(time_value, "hour"):
        return time_value.hour * 60 + time_value.minute
    parts = str(time_value).split(":")
    return int(parts[0]) * 60 + int(parts[1])


def validate_date_range(start_date, end_date):
    """
    Validate that start_date is not after end_date.

    Returns:
        (is_valid, error_message) tuple.
        is_valid is True if the range is valid.
    """
    if start_date and end_date and end_date < start_date:
        return False, "La date de fin doit etre apres ou egale a la date de debut."
    return True, None


def validate_time_range(start_time, end_time):
    """
    Validate that start_time is before end_time.

    Returns:
        (is_valid, error_message) tuple.
    """
    if start_time and end_time:
        start_min = time_to_minutes(start_time)
        end_min = time_to_minutes(end_time)
        if end_min <= start_min:
            return False, "L'heure de fin doit etre apres l'heure de debut."
    return True, None


def validate_working_hours(start_time, end_time):
    """
    Validate that the time range falls within working hours (08:00-17:00).

    Working hours: 08:00-12:00 and 13:00-17:00 (lunch break excluded).

    Returns:
        (is_valid, error_message) tuple.
    """
    if not start_time or not end_time:
        return True, None

    start_min = time_to_minutes(start_time)
    end_min = time_to_minutes(end_time)

    # Check if start is before working hours
    if start_min < WORK_START_MORNING:
        return False, "L'heure de debut ne peut pas etre avant 08:00."

    # Check if end is after working hours
    if end_min > WORK_END_AFTERNOON:
        return False, "L'heure de fin ne peut pas etre apres 17:00."

    # Check if the range covers any working time
    morning_overlap = max(0, min(end_min, WORK_END_MORNING) - max(start_min, WORK_START_MORNING))
    afternoon_overlap = max(0, min(end_min, WORK_END_AFTERNOON) - max(start_min, WORK_START_AFTERNOON))
    total_working_minutes = morning_overlap + afternoon_overlap

    if total_working_minutes <= 0:
        return False, "La plage horaire choisie ne couvre aucun temps de travail."

    return True, None


def count_business_days(start_date, end_date, exclude_weekends=True):
    """
    Count the number of business days between start_date and end_date (inclusive).

    By default, weekends (Saturday and Sunday) are excluded.

    Args:
        start_date: datetime.date
        end_date: datetime.date
        exclude_weekends: bool, if True, Saturday and Sunday are excluded

    Returns:
        int: number of business days
    """
    if not start_date or not end_date:
        return 0

    total_days = (end_date - start_date).days + 1
    if not exclude_weekends:
        return total_days

    business_days = 0
    for day_offset in range(total_days):
        current_date = start_date + timedelta(days=day_offset)
        if current_date.weekday() < 5:  # Monday=0, Sunday=6
            business_days += 1
    return business_days


def calculate_partial_day_days(start_time, end_time):
    """
    Calculate the fraction of a day worked based on start_time and end_time.

    Working hours: 08:00-12:00 and 13:00-17:00 (lunch break excluded).
    Full day = 8 hours = 480 minutes.

    Returns:
        Decimal: fraction of a day (0.0 to 1.0)
    """
    if not start_time or not end_time:
        return Decimal("0.0")

    start_min = time_to_minutes(start_time)
    end_min = time_to_minutes(end_time)

    if end_min <= start_min:
        return Decimal("0.0")

    total_minutes = 0

    # Morning overlap (08:00-12:00)
    morning_start = max(start_min, WORK_START_MORNING)
    morning_end = min(end_min, WORK_END_MORNING)
    if morning_end > morning_start:
        total_minutes += morning_end - morning_start

    # Afternoon overlap (13:00-17:00)
    afternoon_start = max(start_min, WORK_START_AFTERNOON)
    afternoon_end = min(end_min, WORK_END_AFTERNOON)
    if afternoon_end > afternoon_start:
        total_minutes += afternoon_end - afternoon_start

    days = Decimal(str(total_minutes)) / Decimal(str(FULL_DAY_MINUTES))
    return days.quantize(Decimal("0.001"))


def detect_staff_request_overlap(employee, start_date, end_date, exclude_weekends=True,
                                  request_type=None, exclude_request_id=None):
    """
    Detect if a staff request overlaps with existing approved/submitted requests
    for the same employee.

    Overlap is detected when two requests for the same employee have overlapping
    date ranges. This applies to leave and absence requests.

    Args:
        employee: EmployeeProfile instance
        start_date: proposed start date
        end_date: proposed end date
        exclude_weekends: whether weekends are excluded (affects the comparison)
        request_type: filter by request type (optional)
        exclude_request_id: ID of the request being edited (to exclude itself)

    Returns:
        (has_overlap, conflicting_request) tuple.
        has_overlap is True if a conflict is found.
    """
    from apps.requests_management.models import StaffRequest

    if not start_date or not end_date:
        return False, None

    # Only check for leave and absence requests (not recovery, which uses lines)
    conflict_types = [StaffRequest.TYPE_LEAVE, StaffRequest.TYPE_ABSENCE]
    if request_type and request_type in conflict_types:
        conflict_types = [request_type]

    queryset = StaffRequest.objects.filter(
        employee=employee,
        request_type__in=conflict_types,
        status__in=[
            StaffRequest.STATUS_SUBMITTED,
            StaffRequest.STATUS_APPROVED,
        ],
        start_date__isnull=False,
        end_date__isnull=False,
    )

    if exclude_request_id:
        queryset = queryset.exclude(pk=exclude_request_id)

    for existing in queryset:
        existing_start = existing.start_date
        existing_end = existing.end_date

        # Check for date overlap: ranges overlap if start1 <= end2 AND start2 <= end1
        if start_date <= existing_end and existing_start <= end_date:
            return True, existing

    return False, None


def detect_hr_event_overlap(employee, start_date, end_date, exclude_event_id=None):
    """
    Detect if an HR event overlaps with existing active HR events for the same employee.

    Args:
        employee: EmployeeProfile instance
        start_date: proposed start date
        end_date: proposed end date
        exclude_event_id: ID of the event being edited (to exclude itself)

    Returns:
        (has_overlap, conflicting_event) tuple.
    """
    from apps.hr_events.models import HREvent

    if not start_date or not end_date:
        return False, None

    queryset = HREvent.objects.filter(
        employee=employee,
        status=HREvent.STATUS_ACTIVE,
        start_date__isnull=False,
        end_date__isnull=False,
    )

    if exclude_event_id:
        queryset = queryset.exclude(pk=exclude_event_id)

    for existing in queryset:
        existing_start = existing.start_date
        existing_end = existing.end_date

        if start_date <= existing_end and existing_start <= end_date:
            return True, existing

    return False, None


def detect_recovery_line_overlap(request, work_date, start_time, end_time, exclude_line_id=None):
    """
    Detect if a recovery line overlaps with existing recovery lines for the same
    request on the same date.

    Args:
        request: StaffRequest instance (the recovery request)
        work_date: proposed work date
        start_time: proposed start time
        end_time: proposed end time
        exclude_line_id: ID of the line being edited (to exclude itself)

    Returns:
        (has_overlap, conflicting_line) tuple.
    """
    from apps.requests_management.models import RecoveryLine

    if not work_date or not start_time or not end_time:
        return False, None

    start_min = time_to_minutes(start_time)
    end_min = time_to_minutes(end_time)

    queryset = RecoveryLine.objects.filter(
        request=request,
        work_date=work_date,
    )

    if exclude_line_id:
        queryset = queryset.exclude(pk=exclude_line_id)

    for existing in queryset:
        existing_start = time_to_minutes(existing.start_time)
        existing_end = time_to_minutes(existing.end_time)

        # Check for time overlap on the same date
        if start_min < existing_end and existing_start < end_min:
            return True, existing

    return False, None
