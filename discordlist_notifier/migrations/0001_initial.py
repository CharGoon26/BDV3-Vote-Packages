from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DiscordGGConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "webhook_secret",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Paste the DiscordList webhook secret or token here.",
                        max_length=255,
                    ),
                ),
                (
                    "vote_url",
                    models.URLField(
                        blank=True,
                        default="",
                        help_text="Paste the DiscordList vote link here.",
                    ),
                ),
                (
                    "notification_channel_id",
                    models.PositiveBigIntegerField(
                        blank=True,
                        default=None,
                        help_text="Optional Discord channel ID used for vote notifications.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "DiscordList configuration",
                "verbose_name_plural": "DiscordList configurations",
            },
        ),
    ]
