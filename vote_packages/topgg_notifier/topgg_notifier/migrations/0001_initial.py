from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TopGGConfig",
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
                        help_text="Paste the Top.gg webhook secret here. Top.gg uses this to sign vote webhooks.",
                        max_length=255,
                    ),
                ),
                (
                    "bot_id",
                    models.PositiveBigIntegerField(
                        blank=True,
                        default=None,
                        help_text="Your Discord application or bot ID. Used to build the default Top.gg vote link.",
                        null=True,
                    ),
                ),
                (
                    "custom_vote_url",
                    models.URLField(
                        blank=True,
                        default="",
                        help_text="Optional override for the vote button URL. Leave empty to use the standard Top.gg vote link.",
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
                "verbose_name": "Top.gg configuration",
                "verbose_name_plural": "Top.gg configurations",
            },
        ),
    ]
