"""
Service métier centralisé pour la gestion des congés par année (fenêtre glissante de 3 ans).

Logique :
- Chaque employé acquiert 30 jours de congé par année civile.
- Les congés de l'année en cours (N) ne sont PAS consommables.
- Les congés de N-1 et N-2 sont consommables.
- Consommation oldest-first (N-2 avant N-1).
- Changement d'année : suppression de N-3, création de N (bloqué), déblocage de N-1.
- Toute la logique est centralisée ici pour éviter les duplications.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.personnel.models import AnnualLeave

DEFAULT_ANNUAL_QUOTA = Decimal("30")
DEFAULT_WINDOW_SIZE = 3


def get_current_year():
    """Retourne l'année civile courante du serveur."""
    return timezone.localdate().year


def get_annual_quota():
    """
    Retourne le quota annuel de conge configurable.

    Priorité :
    1. LoginBranding.annual_leave_quota (paramètre RH)
    2. DEFAULT_ANNUAL_QUOTA (30) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding and branding.annual_leave_quota is not None:
            return branding.annual_leave_quota
    except Exception:
        pass
    return DEFAULT_ANNUAL_QUOTA


def get_leave_window_size():
    """
    Retourne la taille de la fenêtre glissante configurable.

    Priorité :
    1. LoginBranding.leave_window_size (paramètre RH)
    2. DEFAULT_WINDOW_SIZE (3) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding and branding.leave_window_size is not None:
            return branding.leave_window_size
    except Exception:
        pass
    return DEFAULT_WINDOW_SIZE


def get_leave_window_years(year=None):
    """Retourne les années de la fenêtre glissante : [N-(size-1), ..., N-1, N]."""
    if year is None:
        year = get_current_year()
    size = get_leave_window_size()
    return [year - (size - 1 - i) for i in range(size)]


def ensure_leave_window(profile):
    """
    Vérifie et corrige la fenêtre de congés pour un employé.

    - Supprime les enregistrements dont l'année < N-(size-1).
    - Crée l'enregistrement de l'année N (bloqué, quota=30) s'il n'existe pas.
    - Débloque les années N-1 et N-2 (elles doivent être consommables).
    - Marque l'année N comme bloquée.

    Appelée à chaque accès au tableau de bord / paramètres pour garantir
    la cohérence sans tâche planifiée externe.
    """
    current_year = get_current_year()
    window_years = get_leave_window_years(current_year)
    window_start = window_years[0]

    with transaction.atomic():
        # 1. Supprimer les années obsolètes (N-size et plus)
        AnnualLeave.objects.filter(employee=profile, year__lt=window_start).delete()

        # 2. S'assurer que chaque année de la fenêtre a un enregistrement
        annual_quota = get_annual_quota()
        for year in window_years:
            is_blocked = year == current_year
            obj, created = AnnualLeave.objects.get_or_create(
                employee=profile,
                year=year,
                defaults={
                    "quota": annual_quota,
                    "consumed": Decimal("0"),
                    "is_blocked": is_blocked,
                },
            )
            if not created:
                # Corriger le quota et le statut de blocage si nécessaire
                needs_save = False
                if obj.quota != annual_quota:
                    obj.quota = annual_quota
                    needs_save = True
                if obj.is_blocked != is_blocked:
                    obj.is_blocked = is_blocked
                    needs_save = True
                if needs_save:
                    obj.save(update_fields=["quota", "is_blocked", "updated_at"])

        # 3. Nettoyer les éventuels doublons (années en dehors de la fenêtre)
        AnnualLeave.objects.filter(employee=profile, year__gt=window_years[-1]).delete()


def get_consumable_annual_leaves(profile):
    """
    Retourne les AnnualLeave consommables (non bloqués) de l'employé,
    triés par année croissante (oldest-first).
    """
    ensure_leave_window(profile)
    return AnnualLeave.objects.filter(
        employee=profile, is_blocked=False
    ).order_by("year")


def get_annual_leaves_for_window(profile):
    """
    Retourne tous les AnnualLeave de la fenêtre glissante,
    triés par année croissante. Crée les enregistrements manquants.
    """
    ensure_leave_window(profile)
    return AnnualLeave.objects.filter(employee=profile).order_by("year")


def get_leave_balance(profile):
    """
    Calcule le solde de congé consommable total (somme des restants
    des années non bloquées).
    """
    consumable = get_consumable_annual_leaves(profile)
    total = Decimal("0")
    for al in consumable:
        remaining = al.quota - al.consumed
        if remaining > 0:
            total += remaining
    return total


def get_leave_dashboard_data(profile):
    """
    Retourne les données pour le tableau de bord :
    liste de dictionnaires (un par année de la fenêtre) avec :
    - year
    - quota
    - consumed
    - remaining (quota - consumed)
    - is_blocked
    - is_available (not is_blocked)
    """
    ensure_leave_window(profile)
    window_years = get_leave_window_years()
    leaves_by_year = {
        al.year: al for al in AnnualLeave.objects.filter(
            employee=profile, year__in=window_years
        )
    }

    result = []
    for year in window_years:
        al = leaves_by_year.get(year)
        if al:
            quota = al.quota
            consumed = al.consumed
            remaining = quota - consumed
            is_blocked = al.is_blocked
        else:
            quota = Decimal("0")
            consumed = Decimal("0")
            remaining = Decimal("0")
            is_blocked = year == get_current_year()

        result.append({
            "year": year,
            "quota": quota,
            "consumed": consumed,
            "remaining": remaining,
            "is_blocked": is_blocked,
            "is_available": not is_blocked,
        })
    return result


def consume_leave(profile, amount):
    """
    Consomme `amount` jours de congé de l'employé, oldest-first.

    Retourne un dictionnaire de répartition : {"2024": Decimal("5"), "2025": Decimal("3")}
    ou None si le solde est insuffisant.
    """
    if amount <= 0:
        return {}

    amount = Decimal(str(amount))
    consumable = list(get_consumable_annual_leaves(profile))

    total_available = Decimal("0")
    for al in consumable:
        remaining = al.quota - al.consumed
        if remaining > 0:
            total_available += remaining

    if total_available < amount:
        return None

    breakdown = {}
    remaining_to_consume = amount

    with transaction.atomic():
        for al in consumable:
            if remaining_to_consume <= 0:
                break
            available = al.quota - al.consumed
            if available <= 0:
                continue
            consume_from_this = min(available, remaining_to_consume)
            al.consumed += consume_from_this
            al.save(update_fields=["consumed", "updated_at"])
            breakdown[str(al.year)] = consume_from_this
            remaining_to_consume -= consume_from_this

    return breakdown


def restore_leave(profile, breakdown):
    """
    Restaure les jours consommés selon la répartition `breakdown`.
    Utilisé lors de l'annulation / suppression d'une demande de congé.

    `breakdown` est un dict : {"2024": Decimal("5"), "2025": Decimal("3")}
    """
    if not breakdown:
        return

    with transaction.atomic():
        for year_str, amount in breakdown.items():
            try:
                year = int(year_str)
            except (ValueError, TypeError):
                continue
            amount = Decimal(str(amount))
            if amount <= 0:
                continue
            try:
                al = AnnualLeave.objects.get(employee=profile, year=year)
                al.consumed = max(Decimal("0"), al.consumed - amount)
                al.save(update_fields=["consumed", "updated_at"])
            except AnnualLeave.DoesNotExist:
                pass


def migrate_leave_balance(profile, old_balance):
    """
    Migration des données : crée les enregistrements AnnualLeave
    à partir de l'ancien solde unique `leave_balance`.

    Distribue l'ancien solde sur les années consommables,
    oldest-first, puis crée l'année N bloquée.
    """
    current_year = get_current_year()
    old_balance = Decimal(str(old_balance))
    window_years = get_leave_window_years(current_year)

    with transaction.atomic():
        # Années consommables : toutes sauf l'année courante
        consumable_years = [y for y in window_years if y != current_year]
        remaining_to_distribute = old_balance

        for year in consumable_years:
            remaining = min(remaining_to_distribute, DEFAULT_ANNUAL_QUOTA)
            consumed = DEFAULT_ANNUAL_QUOTA - remaining
            AnnualLeave.objects.get_or_create(
                employee=profile,
                year=year,
                defaults={
                    "quota": DEFAULT_ANNUAL_QUOTA,
                    "consumed": consumed,
                    "is_blocked": False,
                },
            )
            remaining_to_distribute -= remaining

        # Année courante : bloquée
        AnnualLeave.objects.get_or_create(
            employee=profile,
            year=current_year,
            defaults={
                "quota": DEFAULT_ANNUAL_QUOTA,
                "consumed": Decimal("0"),
                "is_blocked": True,
            },
        )


def get_consumable_years_list(profile):
    """Retourne la liste des années consommables (non bloquées) de l'employé."""
    return [
        al.year for al in get_consumable_annual_leaves(profile)
    ]


def save_leave_balances_from_form(profile, year_balances):
    """
    Met à jour les soldes de congés pour un employé à partir d'un dictionnaire
    {year: quota_value} reçu du formulaire de création/modification.

    - Pour chaque année, crée ou met à jour l'enregistrement AnnualLeave.
    - Le quota est défini à la valeur fournie.
    - is_blocked est défini à True pour l'année courante, False sinon.
    - Les années obsolètes (hors fenêtre) sont supprimées.
    """
    from decimal import Decimal as Dec

    current_year = get_current_year()
    window_years = get_leave_window_years(current_year)
    annual_quota = get_annual_quota()

    with transaction.atomic():
        # Supprimer les années obsolètes
        AnnualLeave.objects.filter(
            employee=profile, year__lt=window_years[0]
        ).delete()
        AnnualLeave.objects.filter(
            employee=profile, year__gt=window_years[-1]
        ).delete()

        for year in window_years:
            quota_value = year_balances.get(year, annual_quota)
            try:
                quota_value = Dec(str(quota_value))
            except (ValueError, TypeError):
                quota_value = annual_quota

            is_blocked = year == current_year
            obj, created = AnnualLeave.objects.get_or_create(
                employee=profile,
                year=year,
                defaults={
                    "quota": quota_value,
                    "consumed": Dec("0"),
                    "is_blocked": is_blocked,
                },
            )
            if not created:
                obj.quota = quota_value
                if obj.is_blocked != is_blocked:
                    obj.is_blocked = is_blocked
                obj.save(update_fields=["quota", "is_blocked", "updated_at"])
