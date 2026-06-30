from django.contrib import admin

from .models import DiscordBotListConfig


@admin.register(DiscordBotListConfig)
class DiscordBotListConfigAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("vote_url", "notification_channel_id")
    fields = ("webhook_secret", "vote_url", "notification_channel_id")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and DiscordBotListConfig.objects.first() is None

    def has_delete_permission(self, request, obj=None):
        return False
