from django.urls import path

from .views import botlistme_vote_webhook

app_name = "botlistme_notifier"

urlpatterns = [
    path("webhook", botlistme_vote_webhook, name="webhook"),
    path("webhook/", botlistme_vote_webhook, name="webhook-slash"),
]
