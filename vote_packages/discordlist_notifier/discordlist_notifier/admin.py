from django.contrib import admin

from .models import DiscordGGConfig


@admin.register(DiscordGGConfig)
class DiscordGGConfigAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("vote_url", "notification_channel_id")
    fields = ("webhook_secret", "vote_url", "notification_channel_id")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and DiscordGGConfig.objects.first() is None

    def has_delete_permission(self, request, obj=None):
        return False
