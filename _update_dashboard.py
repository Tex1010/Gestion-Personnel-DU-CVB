with open('templates/personnel/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add three new stat cards after the recovery card, before "Demandes recentes"
old_cards = """        <article class="card stat-card accent-slate">
            <span>Demandes recentes</span>"""

new_cards = """        <article class="card stat-card accent-rose">
            <span>Evenement familial</span>
            <strong id="employee-family-event-remaining">{{ profile.family_event_remaining }} jours</strong>
            <small>Jours restants (10 par an, reinitialise annuellement)</small>
        </article>
        <article class="card stat-card accent-teal">
            <span>Repos medical</span>
            <strong id="employee-medical-leave-total">{{ profile.medical_leave_total }} jours</strong>
            <small>Total de repos medical accumule</small>
        </article>
        <article class="card stat-card accent-indigo">
            <span>Absence maladie</span>
            <strong id="employee-sick-absence-total">{{ profile.sick_absence_total }} jours</strong>
            <small>Total d'absence maladie accumule</small>
        </article>
        <article class="card stat-card accent-slate">
            <span>Demandes recentes</span>"""

content = content.replace(old_cards, new_cards, 1)

# 2. Add JS to refresh the new elements in refreshEmployeeDashboard
old_js = """            if (leaveBalance) leaveBalance.innerText = translateEmployeeText(data.leave_balance);
            if (recoveryBalance) recoveryBalance.innerText = translateEmployeeText(data.recovery_balance);"""

new_js = """            if (leaveBalance) leaveBalance.innerText = translateEmployeeText(data.leave_balance);
            if (recoveryBalance) recoveryBalance.innerText = translateEmployeeText(data.recovery_balance);
            const familyEventRemaining = document.getElementById("employee-family-event-remaining");
            const medicalLeaveTotal = document.getElementById("employee-medical-leave-total");
            const sickAbsenceTotal = document.getElementById("employee-sick-absence-total");
            if (familyEventRemaining) familyEventRemaining.innerText = data.family_event_remaining + " jours";
            if (medicalLeaveTotal) medicalLeaveTotal.innerText = data.medical_leave_total + " jours";
            if (sickAbsenceTotal) sickAbsenceTotal.innerText = data.sick_absence_total + " jours";"""

content = content.replace(old_js, new_js, 1)

with open('templates/personnel/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('dashboard.html updated successfully')
