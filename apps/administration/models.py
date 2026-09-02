from django.conf import settings
from django.db import models

from apps.requests_management.models import StaffRequest


class LoginBranding(models.Model):
    site_name = models.CharField(max_length=120, default="Centre ValBio")
    subtitle = models.CharField(
        max_length=255,
        default="Centre International pour la Valorisation de la Biodiversite",
    )
    address = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=255, blank=True)
    announcement = models.CharField(
        max_length=255,
        blank=True,
        help_text="Texte libre modifiable par l'admin pour annoncer un evenement.",
    )
    request_submission_email_enabled = models.BooleanField(
        default=True,
        help_text="Active l'envoi d'un email a l'adresse de la Ressource Humain (RH) a chaque nouvelle demande.",
    )
    annual_leave_quota = models.DecimalField(
        "Quota annuel de conge",
        max_digits=6,
        decimal_places=1,
        default=30,
        help_text="Nombre de jours de conge acquis chaque annee civile. Les droits de l'annee en cours sont bloques jusqu'a l'annee suivante.",
    )
    leave_window_size = models.PositiveIntegerField(
        "Taille de la fenetre de conges",
        default=3,
        help_text="Nombre d'annees conservees dans la fenetre glissante (ex: 3 = N-2, N-1, N).",
    )
    leave_rules = models.TextField(
        "Regles generales de conges",
        blank=True,
        default="Les droits de l'annee en cours (N) sont bloques jusqu'a l'annee suivante. La consommation s'effectue oldest-first (N-2 avant N-1).",
        help_text="Regles generales affichees dans l'interface de gestion des conges.",
    )
    absence_limit_enabled = models.BooleanField(
        "Activer la limite annuelle des absences",
        default=False,
        help_text="Active ou desactive la limite annuelle d'absence pour tous les employes.",
    )
    absence_annual_limit = models.DecimalField(
        "Limite annuelle des absences",
        max_digits=6,
        decimal_places=1,
        default=15,
        help_text="Nombre maximum de jours d'absence qu'un employe peut accumuler par annee.",
    )
    recovery_limit_enabled = models.BooleanField(
        "Activer la limite annuelle des recuperations",
        default=True,
        help_text="Active ou desactive la limite annuelle de recuperation pour tous les employes.",
    )
    recovery_annual_limit = models.DecimalField(
        "Limite annuelle de recuperation",
        max_digits=6,
        decimal_places=1,
        default=15,
        help_text="Nombre maximum de jours de recuperation qu'un employe peut accumuler par annee.",
    )
    profile_photo_editing_enabled = models.BooleanField(
        "Modification de la photo de profil par l'employe",
        default=True,
        help_text="Active ou desactive la possibilite pour les employes de modifier leur photo de profil depuis leur interface.",
    )
    contact_enabled = models.BooleanField(
        "Activer les moyens de contact sur la page de connexion",
        default=True,
        help_text="Affiche ou masque les moyens de contact (WhatsApp, email, Telegram, etc.) sur la page de connexion.",
    )
    whatsapp_enabled = models.BooleanField(
        "Afficher WhatsApp sur la page de connexion",
        default=True,
        help_text="Affiche le bouton de contact WhatsApp sur la page de connexion.",
    )
    whatsapp_number = models.CharField(
        "Numero WhatsApp",
        max_length=20,
        default="+261347794791",
        help_text="Numero WhatsApp au format international (ex: +261 34 77 947 91).",
    )
    email_contact_enabled = models.BooleanField(
        "Afficher Email sur la page de connexion",
        default=False,
        help_text="Affiche le bouton de contact par email sur la page de connexion.",
    )
    email_contact = models.EmailField(
        "Adresse email de contact",
        blank=True,
        help_text="Adresse email utilisee pour le contact sur la page de connexion.",
    )
    telegram_enabled = models.BooleanField(
        "Afficher Telegram sur la page de connexion",
        default=False,
        help_text="Affiche le bouton de contact Telegram sur la page de connexion.",
    )
    telegram_id = models.CharField(
        "Identifiant ou lien Telegram",
        max_length=100,
        blank=True,
        help_text="Identifiant Telegram (ex: @centrevalbio) ou lien complet.",
    )
    twitter_enabled = models.BooleanField(
        "Afficher Twitter / X sur la page de connexion",
        default=False,
        help_text="Affiche le bouton Twitter / X sur la page de connexion.",
    )
    twitter_url = models.URLField(
        "Lien du profil Twitter / X",
        blank=True,
        help_text="URL du profil Twitter / X (ex: https://x.com/centrevalbio).",
    )
    logo_image = models.FileField(upload_to="branding/logos/", blank=True, null=True)
    hero_image = models.FileField(upload_to="branding/", blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Personnalisation connexion"
        verbose_name_plural = "Personnalisations connexion"

    def __str__(self):
        return self.site_name


class RequestActionHistory(models.Model):
    ACTION_APPROVED = "approved"
    ACTION_REJECTED = "rejected"

    ACTION_CHOICES = [
        (ACTION_APPROVED, "Approuvee"),
        (ACTION_REJECTED, "Rejetee"),
    ]

    request = models.ForeignKey(
        StaffRequest, on_delete=models.CASCADE, related_name="admin_history"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_actions",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historique demande"
        verbose_name_plural = "Historiques demandes"

    def __str__(self):
        return f"{self.request} - {self.get_action_display()}"


class Notification(models.Model):
    PRIORITY_INFO = "info"
    PRIORITY_WARNING = "warning"
    PRIORITY_IMPORTANT = "important"

    PRIORITY_CHOICES = [
        (PRIORITY_INFO, "Information"),
        (PRIORITY_WARNING, "Attention"),
        (PRIORITY_IMPORTANT, "Important"),
    ]

    TYPE_REQUEST_CREATED = "request_created"
    TYPE_REQUEST_APPROVED = "request_approved"
    TYPE_REQUEST_REJECTED = "request_rejected"
    TYPE_REQUEST_CANCELLED = "request_cancelled"
    TYPE_REQUEST_STAGE_ADVANCED = "request_stage_advanced"
    TYPE_RECOVERY_LIMIT_REACHED = "recovery_limit_reached"
    TYPE_RECOVERY_LIMIT_NEAR = "recovery_limit_near"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Destinataire",
    )
    title = models.CharField("Titre", max_length=200)
    message = models.TextField("Message")
    priority = models.CharField(
        "Priorite", max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_INFO
    )
    notification_type = models.CharField("Type", max_length=50, default=TYPE_REQUEST_CREATED)
    is_read = models.BooleanField("Lue", default=False)
    link_url = models.CharField("Lien", max_length=500, blank=True)
    request = models.ForeignKey(
        StaffRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    event_key = models.CharField("Cle evenement", max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"


class AccountActionHistory(models.Model):
    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Creation"),
        (ACTION_UPDATED, "Modification"),
        (ACTION_DELETED, "Suppression"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_actions",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="account_action_entries",
    )
    target_username = models.CharField(max_length=150)
    target_display_name = models.CharField(max_length=255, blank=True)
    target_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Historique compte"
        verbose_name_plural = "Historiques comptes"

    def __str__(self):
        return f"{self.target_username} - {self.get_action_display()}"
