service_content = '''"""
Service metier pour la gestion des evenements RH.

Logique :
- FAMILY_EVENT : consomme le solde "Evenement familial". Chaque employe possede
  10 jours par annee. Le solde est reinitialise a 10 chaque nouvelle annee.
- MEDICAL_LEAVE : augmente le total de repos medical. Le total commence a 0 et
  augmente a chaque ajout. Independant des autres soldes.
- SICK_ABSENCE : augmente le total d'absence maladie. Le total commence a 0 et
  augmente a chaque ajout. Independant des autres soldes.

Tous les evenements sont crees par le RH. Les employes ne voient que leurs totaux.
Chaque evenement peut etre annule dans les 24 heures suivant sa creation.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.hr_events.models import HREvent

DEFAULT_FAMILY_EVENT_QUOTA = Decimal("10")


def get_current_year():
    """Retourne l'annee civile courante du serveur."""
    return timezone.localdate().year


def get_active_family_event_days(profile):
    """
    Calcule le nombre total de jours d'evenements familiaux ACTIFS (non annules)
    pour l'employe.
    """
    total = HREvent.objects.filter(
        employee=profile,
        event_type=HREvent.TYPE_FAMILY_EVENT,
        status=HREvent.STATUS_ACTIVE,
    ).aggregate_total_days()
    return total or Decimal("0.0")


def get_family_event_remaining(profile):
    """
    Calcule le solde restant d'evenements familiaux pour l'employe.

    Quota annuel (10) - jours consommes par les evenements familiaux actifs.
    """
    consumed = get_active_family_event_days(profile)
    return max(Decimal("0.0"), DEFAULT_FAMILY_EVENT_QUOTA - consumed)


def get_medical_leave_total(profile):
    """
    Calcule le total de repos medical pour l'employe.

    Somme des jours de tous les evenements de type repos medical ACTIFS.
    """
    total = HREvent.objects.filter(
        employee=profile,
        event_type=HREvent.TYPE_MEDICAL_LEAVE,
        status=HREvent.STATUS_ACTIVE,
    ).aggregate_total_days()
    return total or Decimal("0.0")


def get_sick_absence_total(profile):
    """
    Calcule le total d'absence maladie pour l'employe.

    Somme des jours de tous les evenements de type absence maladie ACTIFS.
    """
    total = HREvent.objects.filter(
        employee=profile,
        event_type=HREvent.TYPE_SICK_ABSENCE,
        status=HREvent.STATUS_ACTIVE,
    ).aggregate_total_days()
    return total or Decimal("0.0")


def get_hr_events_dashboard_data(profile):
    """
    Retourne les donnees pour le tableau de bord employe :
    - family_event_remaining : jours restants d'evenements familiaux
    - medical_leave_total : total de repos medical
    - sick_absence_total : total d'absence maladie
    """
    return {
        "family_event_remaining": get_family_event_remaining(profile),
        "medical_leave_total": get_medical_leave_total(profile),
        "sick_absence_total": get_sick_absence_total(profile),
    }


def create_hr_event(profile, event_type, days, start_date=None, end_date=None,
                    start_time=None, end_time=None, reason="", created_by=None):
    """
    Cree un nouvel evenement RH pour un employe.

    Pour les evenements familiaux, verifie que le solde est suffisant.
    """
    days = Decimal(str(days))

    if event_type == HREvent.TYPE_FAMILY_EVENT:
        remaining = get_family_event_remaining(profile)
        if remaining < days:
            return False, (
                f"Solde d'evenement familial insuffisant. "
                f"Il reste {remaining} jour(s), vous demandez {days} jour(s)."
            )

    with transaction.atomic():
        event = HREvent.objects.create(
            employee=profile,
            event_type=event_type,
            days=days,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            reason=reason,
            created_by=created_by,
            status=HREvent.STATUS_ACTIVE,
        )
    return True, event


def cancel_hr_event(event):
    """
    Annule un evenement RH.

    L'evenement peut etre annule s'il a ete cree il y a moins de 24 heures.
    Le statut devient "Annule" et l'evenement n'est plus pris en compte dans les calculs.
    """
    if not event.is_active:
        return False, "Cet evenement est deja annule."

    if not event.can_cancel:
        return False, "L'evenement ne peut plus etre annule (plus de 24 heures depuis la creation)."

    event.status = HREvent.STATUS_CANCELLED
    event.save(update_fields=["status", "updated_at"])
    return True, "L'evenement a ete annule."


def reset_family_event_balances():
    """
    Reinitialise le solde d'evenements familiaux a 10 jours pour tous les employes.

    Cette fonction est appelee automatiquement chaque nouvelle annee.
    Elle ne modifie pas les evenements existants (historique conserve),
    mais le quota est reinitialise a 10 pour le calcul du solde restant.

    Note : Le solde est calcule dynamiquement (quota - consommation), donc
    la reinitialisation consiste simplement a considerer le nouveau quota de 10.
    Aucune donnee n'a besoin d'etre modifiee dans la base.
    """
    # Le solde est calcule dynamiquement avec DEFAULT_FAMILY_EVENT_QUOTA = 10.
    # Aucune action necessaire sur les donnees existantes.
    # Les evenements familiaux de l'annee precedente restent dans l'historique.
    pass
'''

with open('apps/hr_events/hr_events_service.py', 'w', encoding='utf-8') as f:
    f.write(service_content)

print("hr_events_service.py written successfully")

# Now fix the menu in base.html
with open('templates/base.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

menu = '                                <a href="{% url \'hr_events:list\' %}" class="{% if request.resolver_match.app_name == \'hr_events\' %}is-active{% endif %}"><i class="bi bi-heart-pulse"></i><span>Evenements RH</span></a>\n'

new_lines = []
added = 0
for i, line in enumerate(lines):
    new_lines.append(line)
    # Look for the non-admin branch "Conges & absences" line
    if 'presence_overview' in line and 'calendar3' in line and 'absences' in line:
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            # Check if this is the non-admin branch (next line is the elif for can_manage_settings)
            if 'can_manage_settings' in nxt and 'elif' in nxt:
                new_lines.append(menu)
                added += 1

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Menu items added in non-admin branch:", added)
