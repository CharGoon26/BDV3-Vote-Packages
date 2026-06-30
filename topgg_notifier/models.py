from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class TopGGConfig(models.Model):
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Paste the Top.gg webhook secret here. Top.gg uses this to sign vote webhooks.",
    )
    bot_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Your Discord application or bot ID. Used to build the default Top.gg vote link.",
    )
    custom_vote_url = models.URLField(
        blank=True,
        default="",
        help_text="Optional override for the vote button URL. Leave empty to use the standard Top.gg vote link.",
    )
    notification_channel_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Optional Discord channel ID used for vote notifications.",
    )

    def clean(self) -> None:
        if TopGGConfig.objects.exclude(pk=self.pk).exists():
            raise ValidationError("You can only have one Top.gg configuration.")

    def __str__(self) -> str:
        return "Top.gg configuration"

    def get_vote_url(self) -> str:
        if self.custom_vote_url:
            return self.custom_vote_url
        if self.bot_id:
            return f"https://top.gg/bot/{self.bot_id}/vote"
        return ""

    class Meta:
        verbose_name = "Top.gg configuration"
        verbose_name_plural = "Top.gg configurations"
