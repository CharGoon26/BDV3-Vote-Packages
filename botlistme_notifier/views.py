from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import hmac
import os
import random
import threading
from types import SimpleNamespace

import aiohttp
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from settings.models import settings
from bd_models.models import Player

from .models import BotListMeConfig

log = logging.getLogger("ballsdex.botlistme")


class _RewardBotStub:
    catch_log: set[int] = set()


class _RewardUserStub:
    def __init__(self, user_id: int):
        self.id = user_id

    def __str__(self) -> str:
        return f"BotList.me voter {self.id}"


async def _get_config() -> BotListMeConfig | None:
    return await BotListMeConfig.objects.afirst()


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _decode_jwt(token: str, secret: str) -> dict | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, binascii.Error, ValueError):
        return None

    if header.get("alg") not in {"HS256", "HS384", "HS512"}:
        return None

    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    digest_map = {
        "HS256": hashlib.sha256,
        "HS384": hashlib.sha384,
        "HS512": hashlib.sha512,
    }
    expected = hmac.new(secret.encode("utf-8"), signing_input, digest_map[header["alg"]]).digest()

    try:
        provided = _b64url_decode(parts[2])
    except (binascii.Error, ValueError):
        return None

    if not hmac.compare_digest(expected, provided):
        return None

    if isinstance(payload, dict):
        return payload

    return None


def _load_payload(request: HttpRequest, secret: str | None) -> tuple[dict | None, HttpResponse | None, str]:
    if request.content_type and "application/json" in request.content_type.lower():
        try:
            return json.loads(request.body.decode("utf-8") or "{}"), None, "json"
        except json.JSONDecodeError:
            return None, JsonResponse({"ok": False, "error": "invalid_json"}, status=400), "json"

    if request.POST:
        payload = dict(request.POST.items())
        data_value = payload.get("data")
        if data_value:
            if secret and data_value.count(".") == 2:
                decoded = _decode_jwt(data_value, secret)
                if decoded is not None:
                    return decoded, None, "jwt"
            try:
                return json.loads(data_value), None, "form-json"
            except json.JSONDecodeError:
                return None, JsonResponse({"ok": False, "error": "invalid_json"}, status=400), "form"
        return payload, None, "form"

    raw_body = request.body.decode("utf-8", errors="replace").strip()
    if secret and raw_body.count(".") == 2:
        decoded = _decode_jwt(raw_body, secret)
        if decoded is not None:
            return decoded, None, "jwt"

    try:
        return json.loads(raw_body or "{}"), None, "json"
    except json.JSONDecodeError:
        return None, JsonResponse({"ok": False, "error": "missing_payload"}, status=400), "raw"


def _extract_token(request: HttpRequest, payload: dict | None) -> str | None:
    headers = request.headers
    for key in ("authorization", "x-botlistme-signature", "x-webhook-signature", "x-vote-signature"):
        value = headers.get(key)
        if value:
            return value.strip()

    if not payload:
        return None

    for key in ("verification_token", "token", "secret", "auth", "authorization"):
        value = payload.get(key)
        if value:
            return str(value).strip()

    return None


def _is_authorized(received_token: str | None, expected_token: str | None) -> bool:
    if not expected_token:
        return False
    if not received_token:
        return False

    normalized = received_token.strip()
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()
    if normalized.lower().startswith("token "):
        normalized = normalized[6:].strip()

    return normalized == expected_token.strip()


def _extract_user_id(payload: dict) -> int | None:
    candidates = [
        payload.get("id"),
        payload.get("user_id"),
        payload.get("userId"),
        payload.get("discord_user_id"),
        payload.get("discordUserid"),
        payload.get("discord_userid"),
        payload.get("discord_id"),
        payload.get("platform_id"),
        payload.get("sub"),
    ]

    user = payload.get("user")
    if isinstance(user, dict):
        candidates.extend(
            [
                user.get("id"),
                user.get("user_id"),
                user.get("platform_id"),
            ]
        )
    elif isinstance(user, str):
        candidates.append(user)

    for candidate in candidates:
        if candidate in (None, ""):
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue

    return None


def _extract_vote_id(payload: dict) -> str | None:
    for key in ("vote_id", "id", "event_id", "transaction_id"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _looks_like_test_payload(payload: dict) -> bool:
    if not payload:
        return True

    if payload.get("test") or payload.get("type") == "webhook.test":
        return True

    if _extract_user_id(payload) is None and _extract_vote_id(payload) is None:
        return True

    return False


def _log_payload(payload: dict, payload_source: str) -> None:
    log.warning(
        "DiscordBotList webhook payload source=%s keys=%s payload=%r",
        payload_source,
        sorted(payload.keys()),
        payload,
    )


async def _send_vote_notification(user_id: int, ball, is_new: bool, config: DiscordBotListConfig | None) -> bool:
    token = settings.bot_token or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
    channel_id = None
    if config and config.notification_channel_id:
        channel_id = str(config.notification_channel_id)
    else:
        channel_id = os.environ.get("VOTE_NOTIFICATION_CHANNEL_ID")

    if not token or not channel_id:
        return False

    headers = {"Authorization": f"Bot {token}"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            message_lines = [
                f"<@{user_id}> voted on BotList.me and received **{ball.ball.country}** `#{ball.pk:0X}`.",
                f"ATK: `{ball.attack_bonus:+}%` • HP: `{ball.health_bonus:+}%`",
            ]
            if ball.specialcard:
                message_lines.append(f"Special: {ball.specialcard.name}")
            if is_new:
                message_lines.append("This card was new to their completion.")

            embed = {
                "title": "🎉 New Vote!",
                "description": "\n".join(message_lines),
                "color": 0xFFD700,
            }
            await session.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json={"embeds": [embed]})
        return True
    except asyncio.CancelledError:
        log.warning("BotList.me vote notification was cancelled while contacting Discord")
        return False
    except Exception:
        log.exception("Failed to send BotList.me vote notification to channel")
        return False


def _build_reward_dm(ball, is_new: bool) -> str:
    lines = [
        "Thanks for voting on BotList.me. You received a random card.",
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


async def _send_dm(user_id: int, content: str) -> bool:
    token = settings.bot_token or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
    if not token:
        log.warning("Cannot send BotList.me reward DM: bot token not available in admin-panel env.")
        return False

    headers = {"Authorization": f"Bot {token}"}

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                "https://discord.com/api/v10/users/@me/channels", json={"recipient_id": str(user_id)}
            ) as resp:
                if resp.status >= 400:
                    log.warning(
                        "Failed to open DM channel for user %s (status %s): %s", user_id, resp.status, await resp.text()
                    )
                    return False
                channel_data = await resp.json()

            async with session.post(
                f"https://discord.com/api/v10/channels/{channel_data['id']}/messages", json={"content": content}
            ) as resp:
                if resp.status >= 400:
                    log.warning(
                        "Failed to send BotList.me reward DM to user %s (status %s): %s",
                        user_id,
                        resp.status,
                        await resp.text(),
                    )
                    return False

        return True
    except asyncio.CancelledError:
        log.warning("BotList.me DM send was cancelled while contacting Discord for user %s", user_id)
        return False
    except Exception:
        log.exception("Unexpected error while sending BotList.me reward DM to user %s", user_id)
        return False


async def _process_vote_reward(user_id: int, vote_id: str | None, config: BotListMeConfig | None) -> None:
    try:
        player, _ = await Player.objects.aget_or_create(discord_id=user_id)

        reward_history = list((player.extra_data or {}).get("discordbotlist_vote_rewards", []))
        if vote_id and any(str(entry.get("vote_id")) == vote_id for entry in reward_history):
            log.info("Skipping duplicate BotList.me reward for vote %s / user %s", vote_id, user_id)
            return

        from ballsdex.packages.countryballs.countryball import BallSpawnView
        from bd_models.models import Ball

        countryballs = [b async for b in Ball.objects.filter(enabled=True)]
        if not countryballs:
            log.error("BotList.me reward failed: no enabled balls found in database.")
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
        player.extra_data["discordbotlist_vote_rewards"] = reward_history[-50:]
        await player.asave(update_fields=("extra_data",))

        dm_sent = await _send_dm(user_id, _build_reward_dm(ball, is_new))
        notification_sent = await _send_vote_notification(user_id, ball, is_new, config)

        log.info(
            "Granted BotList.me vote reward to user %s: %s #%s (vote_id=%s, dm_sent=%s, notification_sent=%s)",
            user_id,
            ball.ball.country,
            f"{ball.pk:0X}",
            vote_id,
            dm_sent,
            notification_sent,
        )
    except Exception:
        log.exception("Unexpected error while processing BotList.me vote reward for user %s", user_id)


def _dispatch_vote_reward(user_id: int, vote_id: str | None, config: BotListMeConfig | None) -> None:
    def runner() -> None:
        try:
            asyncio.run(_process_vote_reward(user_id, vote_id, config))
        except Exception:
            log.exception("BotList.me background worker crashed for user %s", user_id)

    thread = threading.Thread(target=runner, daemon=True, name=f"botlistme-vote-{user_id}")
    thread.start()


def _with_cors(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    origin = request.headers.get("origin")
    if origin:
        response["Access-Control-Allow-Origin"] = origin
        response["Vary"] = "Origin"
    else:
        response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    request_headers = request.headers.get("access-control-request-headers")
    if request_headers:
        response["Access-Control-Allow-Headers"] = request_headers
    else:
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Requested-With, Accept"
    response["Access-Control-Max-Age"] = "600"
    response["Access-Control-Allow-Credentials"] = "true"
    return response


@csrf_exempt
async def botlistme_vote_webhook(request: HttpRequest) -> HttpResponse:
    if request.method == "OPTIONS":
        return _with_cors(request, HttpResponse(status=204))
    if request.method != "POST":
        return _with_cors(request, HttpResponse(status=405))

    config = await _get_config()
    expected_token = config.webhook_secret if config and config.webhook_secret else None
    payload, error_response, payload_source = _load_payload(request, expected_token)
    if error_response:
        return _with_cors(request, error_response)
    assert payload is not None
    _log_payload(payload, payload_source)

    if not expected_token:
        log.warning("BotList.me webhook secret is not configured.")
        return _with_cors(request, HttpResponse(status=401))

    if payload.get("is_test") or payload.get("test") or payload.get("type") == "webhook.test":
        return _with_cors(request, JsonResponse({"ok": True, "test": True}, status=200))

    user_id = _extract_user_id(payload)
    if user_id is None:
        if _looks_like_test_payload(payload):
            return _with_cors(request, JsonResponse({"ok": True, "test": True}, status=200))
        log.warning("BotList.me webhook payload did not contain a usable user id.")
        return _with_cors(request, JsonResponse({"ok": False, "error": "missing_user_id"}, status=400))

    vote_id = _extract_vote_id(payload)
    _dispatch_vote_reward(user_id, vote_id, config)
    return _with_cors(request, JsonResponse({"ok": True, "queued": True, "user_id": user_id, "vote_id": vote_id}, status=200))
