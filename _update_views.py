with open('apps/personnel/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
old_import = """from apps.accounts.utils import get_user_profile, normalize_portal_role
from apps.administration.models import LoginBranding
from apps.personnel.models import Role
from apps.requests_management.models import StaffRequest"""

new_import = """from apps.accounts.utils import get_user_profile, normalize_portal_role
from apps.administration.models import LoginBranding
from apps.hr_events.hr_events_service import get_hr_events_dashboard_data
from apps.personnel.models import Role
from apps.requests_management.models import StaffRequest"""

content = content.replace(old_import, new_import, 1)

# 2. Add hr_events_data to dashboard_view context
old_context = """        "leave_window_data": profile.leave_window_data,
    }
    return render(request, "personnel/dashboard.html", context)"""

new_context = """        "leave_window_data": profile.leave_window_data,
        "hr_events_data": get_hr_events_dashboard_data(profile),
    }
    return render(request, "personnel/dashboard.html", context)"""

content = content.replace(old_context, new_context, 1)

# 3. Add hr_events data to dashboard_data_view JSON response
old_json = """            "leave_balance": f"{format_decimal(profile.leave_balance)} jours",
            "recovery_balance": f"{format_decimal(profile.recovery_balance)} jours","""

new_json = """            "leave_balance": f"{format_decimal(profile.leave_balance)} jours",
            "recovery_balance": f"{format_decimal(profile.recovery_balance)} jours",
            "family_event_remaining": format_decimal(profile.family_event_remaining),
            "medical_leave_total": format_decimal(profile.medical_leave_total),
            "sick_absence_total": format_decimal(profile.sick_absence_total),"""

content = content.replace(old_json, new_json, 1)

with open('apps/personnel/views.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('views.py updated successfully')
