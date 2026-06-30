from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models


class DiscordBotListConfig(models.Model):
    webhook_secret = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Paste the DiscordBotList webhook secret or token here.",
    )
    vote_url = models.URLField(
        blank=True,
        default="",
        help_text="Paste the DiscordBotList vote link here.",
    )
    notification_channel_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Optional Discord channel ID used for vote notifications.",
    )

    def clean(self) -> None:
        if DiscordBotListConfig.objects.exclude(pk=self.pk).exists():
            raise ValidationError("You can only have one DiscordBotList configuration.")

    def __str__(self) -> str:
        return "DiscordBotList configuration"

    class Meta:
        verbose_name = "DiscordBotList configuration"
        verbose_name_plural = "DiscordBotList configurations"
