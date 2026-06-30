from django.urls import path

from .views import discordlist_vote_webhook

app_name = "discordlist_notifier"

urlpatterns = [
    path("webhook", discordlist_vote_webhook, name="webhook"),
    path("webhook/", discordlist_vote_webhook, name="webhook-slash"),
]
