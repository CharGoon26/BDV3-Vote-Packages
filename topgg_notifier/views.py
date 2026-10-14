from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import threading
from types import SimpleNamespace

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from vote_links.vote_notifier import get_vote_notifier

from bd_models.models import Player

from .models import TopGGConfig

log = logging.getLogger("ballsdex.topgg")


def _run_in_fresh_thread(coro) -> None:
    """Run a coroutine in a dedicated thread with its own event loop.

    asgiref's thread-sensitive ``sync_to_async`` relies on a
    ``CurrentThreadExecutor`` that is tied to the request thread and marked
    broken once the request finishes. Scheduling the reward work with
    ``asyncio.create_task`` defers it past that point, so the DB call fails
    with "CurrentThreadExecutor already quit or is broken". Running the
    coroutine in a fresh thread with a new loop gives it an independent
    executor that stays alive for the whole task.
    """

    def _runner() -> None:
        try:
            asyncio.run(coro)
        except Exception:
            log.exception("Unexpected error in reward thread")

    threading.Thread(target=_runner, daemon=True).start()



class _RewardBotStub:
    """Minimal bot stub so we can reuse BallSpawnView.catch_ball() outside the bot process."""

    catch_log: set[int] = set()


class _RewardUserStub:
    def __init__(self, user_id: int):
        self.id = user_id

    def __str__(self) -> str:
        return f"Top.gg voter {self.id}"


async def _get_config() -> TopGGConfig | None:
    return await TopGGConfig.objects.afirst()


def _parse_signature_header(header_value: str | None) -> tuple[str | None, str | None]:
    if not header_value:
        return None, None

    timestamp = None
    signature = None

    for part in header_value.split(","):
        part = part.strip()
        if part.startswith("t="):
            timestamp = part[2:]
        elif part.startswith("v1="):
            signature = part[3:]

    return timestamp, signature


def _verify_topgg_signature(raw_body: bytes, signature_header: str | None, secret: str | None) -> bool:
    if not secret:
        log.warning("Top.gg webhook secret is not configured.")
        return False

    timestamp, provided_signature = _parse_signature_header(signature_header)
    if not timestamp or not provided_signature:
        return False

    signed_payload = timestamp.encode("utf-8") + b"." + raw_body
    expected_signature = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_signature, provided_signature)


def _build_reward_dm(ball, is_new: bool) -> str:
    lines = [
        "Thanks for voting on Top.gg. You received a random card.",
        "",
        f"**{ball.ball.country}** `#{ball.pk:0X}`",
        f"ATK: `{ball.attack_bonus:+}%` • HP: `{ball.health_bonus:+}%`",
    ]

    if ball.specialcard:
        emoji = str(ball.specialcard.emoji or "").strip()
        special_name = ball.specialcard.name
        if emoji:
            lines.append(f"Special: {emoji} {special_name}")
        else:
            lines.append(f"Special: {special_name}")

    if is_new:
        lines.append("This card was new to your completion.")

    return "\n".join(lines)


def _resolve_vote_id(data: dict) -> str | None:
    vote_id = data.get("id")
    if vote_id is None:
        return None
    return str(vote_id)


async def _process_vote_reward(user_id: int, vote_id: str | None, config: TopGGConfig | None) -> None:
    try:
        player, _ = await Player.objects.aget_or_create(discord_id=user_id)

        reward_history = list((player.extra_data or {}).get("topgg_vote_rewards", []))
        if vote_id and any(str(entry.get("vote_id")) == vote_id for entry in reward_history):
            log.info("Skipping duplicate Top.gg reward for vote %s / user %s", vote_id, user_id)
            return

        from ballsdex.packages.countryballs.countryball import BallSpawnView
        from bd_models.models import Ball

        countryballs = [b async for b in Ball.objects.filter(enabled=True)]
        if not countryballs:
            log.error("Top.gg reward failed: no enabled balls found in database.")
            return

        weights = [b.rarity for b in countryballs]
        chosen_ball = random.choices(population=countryballs, weights=weights, k=1)[0]

        reward_view = BallSpawnView(_RewardBotStub(), chosen_ball)
        reward_view.message = SimpleNamespace(created_at=timezone.now())

        ball, is_new = await reward_view.catch_ball(_RewardUserStub(user_id), player=player, guild=None)

        reward_history.append(
            {
                "vote_id": vote_id,
                "user_id": user_id,
                "ball": ball.ball.country,
                "ball_instance_id": ball.pk,
                "created_at": timezone.now().timestamp(),
                "special": ball.specialcard.name if ball.specialcard else None,
            }
        )
        player.extra_data["topgg_vote_rewards"] = reward_history[-50:]
        await player.asave(update_fields=("extra_data",))

        notifier = get_vote_notifier()

        notification_channel_id = None
        if config and config.notification_channel_id:
            notification_channel_id = config.notification_channel_id
        else:
            env_channel = os.environ.get("VOTE_NOTIFICATION_CHANNEL_ID")
            if env_channel:
                notification_channel_id = int(env_channel)

        dm_sent = await notifier.send_dm(user_id, _build_reward_dm(ball, is_new), "Top.gg")
        notification_sent = await notifier.send_notification(
            user_id, ball, is_new, notification_channel_id, "Top.gg"
        )

        log.info(
            "Granted Top.gg vote reward to user %s: %s #%s (vote_id=%s, dm_sent=%s, notification_sent=%s)",
            user_id,
            ball.ball.country,
            f"{ball.pk:0X}",
            vote_id,
            dm_sent,
            notification_sent,
        )
    except Exception:
        log.exception("Unexpected error while processing Top.gg vote reward for user %s", user_id)


@csrf_exempt
async def topgg_vote_webhook(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    config = await _get_config()
    raw_body = request.body
    secret = None
    if config and config.webhook_secret:
        secret = config.webhook_secret
    else:
        secret = os.environ.get("TOPGG_WEBHOOK_SECRET") or os.environ.get("TOPGG_WEBHOOK_AUTH")

    signature_header = request.headers.get("x-topgg-signature")

    if not _verify_topgg_signature(raw_body, signature_header, secret):
        log.warning("Rejected Top.gg webhook: invalid signature.")
        return HttpResponse(status=401)

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    event_type = payload.get("type")
    data = payload.get("data") or {}

    if event_type == "webhook.test":
        return JsonResponse({"ok": True, "test": True}, status=200)

    if event_type != "vote.create":
        return JsonResponse({"ok": False, "error": "unsupported_event"}, status=400)

    user_data = data.get("user") or {}
    raw_user_id = user_data.get("platform_id")
    vote_id = _resolve_vote_id(data)

    if not raw_user_id:
        return JsonResponse({"ok": False, "error": "missing_user_platform_id"}, status=400)

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_user_platform_id"}, status=400)
    _run_in_fresh_thread(_process_vote_reward(user_id, vote_id, config))

    return JsonResponse(
        {
            "ok": True,
            "queued": True,
            "user_id": user_id,
            "vote_id": vote_id,
        },
        status=200,
    )
