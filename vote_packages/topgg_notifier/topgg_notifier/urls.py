from django.urls import path

from .views import topgg_vote_webhook

app_name = "topgg_notifier"

urlpatterns = [
    path("webhook", topgg_vote_webhook, name="webhook"),
    path("webhook/", topgg_vote_webhook, name="webhook-slash"),
]
