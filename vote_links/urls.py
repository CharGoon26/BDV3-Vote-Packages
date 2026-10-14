from __future__ import annotations

import importlib
import logging

from django.urls import include, path

log = logging.getLogger("ballsdex.vote_links")

# Each vote notifier package exposes a ``urls`` module with ``app_name`` and
# ``urlpatterns``. Include every installed one automatically so the admin
# panel only needs a single ``include("vote_links.urls")`` line and never has
# to list each notifier by hand. Notifiers that are not installed are skipped
# silently, which keeps the package fully standalone.
#
# The mount prefix is the bare site name (e.g. ``discordbotlist``) rather than
# the package name (``discordbotlist_notifier``) so the webhook endpoints stay
# at the exact paths the voting sites POST to.
_NOTIFIERS = (
    ("topgg", "topgg_notifier"),
    ("discordlist", "discordlist_notifier"),
    ("discordbotlist", "discordbotlist_notifier"),
    ("botlistme", "botlistme_notifier"),
)


def _register_vote_webhooks() -> list:
    routes = []
    for site_name, package_name in _NOTIFIERS:
        try:
            importlib.import_module(f"{package_name}.urls")
        except ImportError:
            log.debug("Vote notifier %s is not installed, skipping its webhook route", package_name)
            continue
        routes.append(path(f"{site_name}/", include(f"{package_name}.urls")))
    return routes


urlpatterns = _register_vote_webhooks()
