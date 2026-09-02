"""
Service métier centralisé pour la gestion des récupérations par année
(fenêtre glissante de 3 ans, similaire aux congés).

Logique :
- Chaque employé accumule des jours de récupération par année civile.
- La consommation se fait oldest-first (année la plus ancienne d'abord).
- Une limite annuelle configurable (par défaut 15 jours) peut être activée/désactivée.
- Toute la logique est centralisée ici pour éviter les duplications.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.personnel.models import AnnualRecovery

DEFAULT_RECOVERY_LIMIT = Decimal("15")
DEFAULT_RECOVERY_LIMIT_ENABLED = True
DEFAULT_ABSENCE_LIMIT = Decimal("15")
DEFAULT_ABSENCE_LIMIT_ENABLED = False


def get_current_year():
    """Retourne l'année civile courante du serveur."""
    return timezone.localdate().year


def get_recovery_limit():
    """
    Retourne la limite annuelle de récupération configurable.

    Priorité :
    1. LoginBranding.recovery_annual_limit (paramètre RH)
    2. DEFAULT_RECOVERY_LIMIT (15) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding and branding.recovery_annual_limit is not None:
            return branding.recovery_annual_limit
    except Exception:
        pass
    return DEFAULT_RECOVERY_LIMIT


def is_recovery_limit_enabled():
    """
    Retourne si la limite annuelle de récupération est activée.

    Priorité :
    1. LoginBranding.recovery_limit_enabled (paramètre RH)
    2. DEFAULT_RECOVERY_LIMIT_ENABLED (True) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding is not None:
            return branding.recovery_limit_enabled
    except Exception:
        pass
    return DEFAULT_RECOVERY_LIMIT_ENABLED


def get_absence_limit():
    """
    Retourne la limite annuelle des absences configurable.

    Priorité :
    1. LoginBranding.absence_annual_limit (paramètre RH)
    2. DEFAULT_ABSENCE_LIMIT (15) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding and branding.absence_annual_limit is not None:
            return branding.absence_annual_limit
    except Exception:
        pass
    return DEFAULT_ABSENCE_LIMIT


def is_absence_limit_enabled():
    """
    Retourne si la limite annuelle des absences est activée.

    Priorité :
    1. LoginBranding.absence_limit_enabled (paramètre RH)
    2. DEFAULT_ABSENCE_LIMIT_ENABLED (False) en fallback
    """
    try:
        from apps.administration.models import LoginBranding

        branding = LoginBranding.objects.first()
        if branding is not None:
            return branding.absence_limit_enabled
    except Exception:
        pass
    return DEFAULT_ABSENCE_LIMIT_ENABLED


def get_recovery_window_years(year=None):
    """Retourne les années de la fenêtre glissante : [N-(size-1), ..., N-1, N]."""
    from apps.personnel.leave_service import get_leave_window_years

    return get_leave_window_years(year)


def ensure_recovery_window(profile):
    """
    Vérifie et corrige la fenêtre de récupérations pour un employé.

    - Supprime les enregistrements dont l'année < N-(size-1).
    - Crée les enregistrements manquants pour chaque année de la fenêtre.
    - Supprime les années au-delà de la fenêtre.

    Appelée à chaque accès au tableau de bord pour garantir la cohérence.
    """
    current_year = get_current_year()
    window_years = get_recovery_window_years(current_year)
    window_start = window_years[0]

    with transaction.atomic():
        # 1. Supprimer les années obsolètes (hors fenêtre)
        AnnualRecovery.objects.filter(employee=profile, year__lt=window_start).delete()
        AnnualRecovery.objects.filter(employee=profile, year__gt=window_years[-1]).delete()

        # 2. S'assurer que chaque année de la fenêtre a un enregistrement
        for year in window_years:
            AnnualRecovery.objects.get_or_create(
                employee=profile,
                year=year,
                defaults={
                    "balance": Decimal("0"),
                    "consumed": Decimal("0"),
                },
            )


def get_recovery_dashboard_data(profile):
    """
    Retourne les données pour le tableau de bord :
    liste de dictionnaires (un par année de la fenêtre) avec :
    - year
    - balance
    - consumed
    - remaining (balance - consumed)
    """
    ensure_recovery_window(profile)
    window_years = get_recovery_window_years()
    recoveries_by_year = {
        ar.year: ar for ar in AnnualRecovery.objects.filter(
            employee=profile, year__in=window_years
        )
    }

    result = []
    for year in window_years:
        ar = recoveries_by_year.get(year)
        if ar:
            balance = ar.balance
            consumed = ar.consumed
            remaining = balance - consumed
        else:
            balance = Decimal("0")
            consumed = Decimal("0")
            remaining = Decimal("0")

        result.append({
            "year": year,
            "balance": balance,
            "consumed": consumed,
            "remaining": remaining,
        })
    return result


def get_recovery_balance(profile):
    """
    Calcule le solde de récupération consommable total
    (somme des restants de toutes les années de la fenêtre).
    """
    ensure_recovery_window(profile)
    total = Decimal("0")
    for ar in AnnualRecovery.objects.filter(employee=profile):
        remaining = ar.balance - ar.consumed
        if remaining > 0:
            total += remaining
    return total


def get_recovery_balance_for_year(profile, year):
    """Retourne le solde restant de récupération pour une année donnée."""
    ensure_recovery_window(profile)
    try:
        ar = AnnualRecovery.objects.get(employee=profile, year=year)
        return ar.balance - ar.consumed
    except AnnualRecovery.DoesNotExist:
        return Decimal("0")


def group_recovery_lines_by_year(line_specs):
    """
    Regroupe des lignes de recuperation par annee civile.

    `line_specs` : iterable de dicts ayant `work_date` et `duration_hours`.
    Retourne {annee: total_jours} (uniquement les annees ayant des jours).
    """
    from collections import defaultdict

    year_amounts = defaultdict(lambda: Decimal("0"))
    for spec in line_specs:
        work_date = spec.get("work_date")
        duration = spec.get("duration_hours")
        if not work_date or duration is None:
            continue
        year_amounts[work_date.year] += Decimal(str(duration))
    return dict(year_amounts)


def check_recovery_request_limit(profile, year_amounts):
    """
    Verifie la limite annuelle de recuperation pour un ensemble de lignes.

    `year_amounts` : dict {annee: montant_jours}.
    Retourne (ok, limit) :
    - ok=False si l'une des annees depasserait la limite configuree.
    - limit : la limite annuelle configuree (meme si desactivee).
    """
    if not is_recovery_limit_enabled():
        return True, get_recovery_limit()
    limit = get_recovery_limit()
    for year, amount in year_amounts.items():
        ok, _message, _remaining = check_recovery_limit(profile, year, amount)
        if not ok:
            return False, limit
    return True, limit


def check_recovery_limit(profile, year, amount):
    """
    Vérifie si l'ajout de `amount` jours de récupération pour `year`
    respecte la limite annuelle configurée.

    Retourne (ok, message, remaining_allowed).
    - ok : True si l'ajout est autorisé.
    - message : message d'erreur si non autorisé.
    - remaining_allowed : jours restants autorisés pour cette année.
    """
    if not is_recovery_limit_enabled():
        return True, "", None

    limit = get_recovery_limit()
    ensure_recovery_window(profile)

    try:
        ar = AnnualRecovery.objects.get(employee=profile, year=year)
        current_balance = ar.balance
    except AnnualRecovery.DoesNotExist:
        current_balance = Decimal("0")

    remaining_allowed = limit - current_balance
    if remaining_allowed < 0:
        remaining_allowed = Decimal("0")

    if current_balance >= limit:
        return (
            False,
            (
                f"Votre solde de récupération pour {year} a atteint la limite autorisée "
                f"({limit} jours). Veuillez effectuer une demande d'absence pour consommer "
                f"votre récupération disponible."
            ),
            remaining_allowed,
        )

    if Decimal(str(amount)) > remaining_allowed:
        return (
            False,
            (
                f"Vous avez atteint la limite de {limit} jours de récupération pour "
                f"cette année. Vous devez effectuer une demande d'absence afin de "
                f"consommer votre solde de récupération."
            ),
            remaining_allowed,
        )

    return True, "", remaining_allowed


def add_recovery(profile, year, amount):
    """
    Ajoute `amount` jours de récupération pour l'année `year`.
    Vérifie la limite annuelle si activée.

    Retourne (ok, message).
    """
    amount = Decimal(str(amount))
    if amount <= 0:
        return False, "Le montant doit être positif."

    ok, message, _ = check_recovery_limit(profile, year, amount)
    if not ok:
        return False, message

    ensure_recovery_window(profile)
    with transaction.atomic():
        ar, created = AnnualRecovery.objects.get_or_create(
            employee=profile,
            year=year,
            defaults={"balance": Decimal("0"), "consumed": Decimal("0")},
        )
        ar.balance += amount
        ar.save(update_fields=["balance", "updated_at"])

    # Notifications intelligentes pour la limite
    if is_recovery_limit_enabled():
        limit = get_recovery_limit()
        try:
            from apps.administration.notifications_service import (
                notify_recovery_limit_near,
                notify_recovery_limit_reached,
            )

            if ar.balance >= limit:
                notify_recovery_limit_reached(profile, year, limit)
            elif ar.balance >= limit * Decimal("0.8"):
                notify_recovery_limit_near(profile, year, ar.balance, limit)
        except Exception:
            pass

    return True, ""


def consume_recovery(profile, amount):
    """
    Consomme `amount` jours de récupération de l'employé, oldest-first.

    Retourne un dictionnaire de répartition : {"2024": Decimal("5"), "2025": Decimal("3")}
    ou None si le solde est insuffisant.
    """
    if amount <= 0:
        return {}

    amount = Decimal(str(amount))
    ensure_recovery_window(profile)
    recoveries = list(
        AnnualRecovery.objects.filter(employee=profile).order_by("year")
    )

    total_available = Decimal("0")
    for ar in recoveries:
        remaining = ar.balance - ar.consumed
        if remaining > 0:
            total_available += remaining

    if total_available < amount:
        return None

    breakdown = {}
    remaining_to_consume = amount

    with transaction.atomic():
        for ar in recoveries:
            if remaining_to_consume <= 0:
                break
            available = ar.balance - ar.consumed
            if available <= 0:
                continue
            consume_from_this = min(available, remaining_to_consume)
            ar.consumed += consume_from_this
            ar.save(update_fields=["consumed", "updated_at"])
            breakdown[str(ar.year)] = float(consume_from_this)
            remaining_to_consume -= consume_from_this

    return breakdown


def restore_recovery(profile, breakdown):
    """
    Restaure les jours consommés selon la répartition `breakdown`.
    Utilisé lors de l'annulation / suppression d'une demande d'absence.

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
                ar = AnnualRecovery.objects.get(employee=profile, year=year)
                ar.consumed = max(Decimal("0"), ar.consumed - amount)
                ar.save(update_fields=["consumed", "updated_at"])
            except AnnualRecovery.DoesNotExist:
                pass


def migrate_recovery_balance(profile, old_balance):
    """
    Migration des données : crée les enregistrements AnnualRecovery
    à partir de l'ancien solde unique `recovery_balance`.

    Distribue l'ancien solde sur les années de la fenêtre, oldest-first.
    """
    old_balance = Decimal(str(old_balance))
    if old_balance <= 0:
        return

    window_years = get_recovery_window_years()
    remaining_to_distribute = old_balance

    with transaction.atomic():
        for year in window_years:
            if remaining_to_distribute <= 0:
                break
            ar, created = AnnualRecovery.objects.get_or_create(
                employee=profile,
                year=year,
                defaults={"balance": Decimal("0"), "consumed": Decimal("0")},
            )
            if created:
                ar.balance = remaining_to_distribute
                ar.save(update_fields=["balance", "updated_at"])
                remaining_to_distribute = Decimal("0")