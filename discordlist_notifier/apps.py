from django.apps import AppConfig


class DiscordGGNotifierConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "discordlist_notifier"
    dpy_package = "discordlist_notifier"
