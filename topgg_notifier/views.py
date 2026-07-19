from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import os
import random
from types import SimpleNamespace

import aiohttp
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from settings.models import settings
from bd_models.models import Player

from .models import TopGGConfig

log = logging.getLogger("ballsdex.topgg")


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


def _generate_card_image(ball) -> tuple[bytes, str, str] | None:
    try:
        from ballsdex.core.image_generator.image_gen import draw_card

        image, save_kwargs = draw_card(ball)
        buffer = io.BytesIO()
        image_format = save_kwargs.get("format", "WEBP")
        image.save(buffer, format=image_format)
        buffer.seek(0)
        image.close()

        ext = str(image_format).lower()
        if ext == "jpeg":
            ext = "jpg"

        content_type = f"image/{ext}"
        if ext == "jpg":
            content_type = "image/jpeg"

        return buffer.getvalue(), f"vote_reward.{ext}", content_type
    except Exception:
        log.exception("Failed to generate Top.gg reward image for ball %s", ball.pk)
        return None


async def _send_dm(user_id: int, content: str, ball=None) -> bool:
    token = settings.bot_token or os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
    if not token:
        log.warning("Cannot send Top.gg reward DM: bot token not available in admin-panel env.")
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

            image_data = _generate_card_image(ball) if ball else None

            if image_data:
                image_bytes, filename, image_content_type = image_data
                form = aiohttp.FormData()
                form.add_field("payload_json", json.dumps({"content": content}), content_type="application/json")
                form.add_field("files[0]", image_bytes, filename=filename, content_type=image_content_type)

                async with session.post(
                    f"https://discord.com/api/v10/channels/{channel_data['id']}/messages", data=form
                ) as resp:
                    if resp.status >= 400:
                        log.warning(
                            "Failed to send Top.gg reward DM with image to user %s (status %s): %s",
                            user_id,
                            resp.status,
                            await resp.text(),
                        )
                        return False
            else:
                async with session.post(
                    f"https://discord.com/api/v10/channels/{channel_data['id']}/messages", json={"content": content}
                ) as resp:
                    if resp.status >= 400:
                        log.warning(
                            "Failed to send Top.gg reward DM to user %s (status %s): %s",
                            user_id,
                            resp.status,
                            await resp.text(),
                        )
                        return False

        return True
    except Exception:
        log.exception("Unexpected error while sending Top.gg reward DM to user %s", user_id)
        return False


async def _send_vote_notification(user_id: int, ball, is_new: bool, config: TopGGConfig | None) -> bool:
    token = settings.bot_token or os.environ.get("DISCORD_TOKEN") or os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN")
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
            description_lines = [
                f"<@{user_id}> voted on Top.gg and received **{ball.ball.country}** `#{ball.pk:0X}`.",
                f"ATK: `{ball.attack_bonus:+}%` • HP: `{ball.health_bonus:+}%`",
            ]
            if ball.specialcard:
                description_lines.append(f"Special: {ball.specialcard.name}")
            if is_new:
                description_lines.append("This card was new to their completion.")

            embed = {
                "title": "🎉 New Vote!",
                "description": "\n".join(description_lines),
                "color": 0xFFD700,
            }
            await session.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json={"embeds": [embed]})
        return True
    except Exception:
        log.exception("Failed to send vote notification to channel")
        return False


def _resolve_vote_id(data: dict) -> str | None:
    vote_id = data.get("id")
    if vote_id is None:
        return None
    return str(vote_id)


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

    player, _ = await Player.objects.aget_or_create(discord_id=user_id)

    reward_history = list((player.extra_data or {}).get("topgg_vote_rewards", []))
    if vote_id and any(str(entry.get("vote_id")) == vote_id for entry in reward_history):
        log.info("Skipping duplicate Top.gg reward for vote %s / user %s", vote_id, user_id)
        return JsonResponse({"ok": True, "deduped": True}, status=200)

    from ballsdex.packages.countryballs.countryball import BallSpawnView
    from bd_models.models import Ball

    countryballs = [b async for b in Ball.objects.filter(enabled=True)]
    if not countryballs:
        log.error("Top.gg reward failed: no enabled balls found in database.")
        return JsonResponse({"ok": False, "error": "no_ball_to_spawn"}, status=500)

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

    dm_sent = await _send_dm(user_id, _build_reward_dm(ball, is_new), ball=ball)
    notification_sent = await _send_vote_notification(user_id, ball, is_new, config)

    log.info(
        "Granted Top.gg vote reward to user %s: %s #%s (vote_id=%s, dm_sent=%s, notification_sent=%s)",
        user_id,
        ball.ball.country,
        f"{ball.pk:0X}",
        vote_id,
        dm_sent,
        notification_sent,
    )

    return JsonResponse(
        {
            "ok": True,
            "vote_id": vote_id,
            "user_id": user_id,
            "ball_instance_id": ball.pk,
            "dm_sent": dm_sent,
            "notification_sent": notification_sent,
        },
        status=200,
    )
