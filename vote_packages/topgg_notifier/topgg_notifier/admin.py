from django.contrib import admin

from .models import TopGGConfig


@admin.register(TopGGConfig)
class TopGGConfigAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = ("bot_id", "notification_channel_id", "vote_url_preview")
    fields = ("webhook_secret", "bot_id", "custom_vote_url", "notification_channel_id")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and TopGGConfig.objects.first() is None

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Vote URL")
    def vote_url_preview(self, obj: TopGGConfig):
        return obj.get_vote_url() or "Set a bot ID or custom vote URL"
