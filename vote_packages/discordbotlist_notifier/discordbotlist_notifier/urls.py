from django.urls import path

from .views import discordbotlist_vote_webhook

app_name = "discordbotlist_notifier"

urlpatterns = [
    path("webhook", discordbotlist_vote_webhook, name="webhook"),
    path("webhook/", discordbotlist_vote_webhook, name="webhook-slash"),
]
