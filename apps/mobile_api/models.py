import secrets

from django.conf import settings
from django.db import models


class MobileSessionToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mobile_session_tokens",
    )
    key = models.CharField(max_length=64, unique=True, db_index=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Jeton mobile"
        verbose_name_plural = "Jetons mobiles"

    def __str__(self):
        return f"{self.user.username} - {self.key[:8]}"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        super().save(*args, **kwargs)
