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
        help_text="Active l'envoi d'un email a l'adresse d'administration a chaque nouvelle demande.",
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
