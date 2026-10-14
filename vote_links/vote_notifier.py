from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    pass

log = logging.getLogger("ballsdex.vote_notifier")


class VoteNotifier:
    """
    Centralized vote notification utility.

    Uses a single shared aiohttp.ClientSession and a semaphore to cap
    concurrent outbound HTTP requests to Discord's API. This replaces
    the per-vote thread + per-request session pattern that caused
    memory bloat under load.
    """

    def __init__(self, max_concurrent: int = 10):
        # Sessions are keyed by their owning event loop. Vote rewards run in
        # their own thread with their own loop (see the notifier views), so a
        # single shared session would be bound to whichever loop created it
        # first and break on every other loop with "Event loop is closed".
        self._sessions: dict[asyncio.AbstractEventLoop, aiohttp.ClientSession] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._bot_token: str | None = None

    def initialize(self, bot_token: str) -> None:
        """Initialize the notifier with a bot token."""
        self._bot_token = bot_token
        log.info("VoteNotifier initialized with bot token")

    def _get_token(self) -> str:
        if self._bot_token:
            return self._bot_token
        # Standalone lazy initialization: fall back to environment variables so
        # the vote notifier works in the admin-panel container without requiring
        # the Discord bot process to be running.
        self._bot_token = (
            os.environ.get("DISCORD_TOKEN")
            or os.environ.get("BOT_TOKEN")
            or os.environ.get("TOKEN")
        )
        if not self._bot_token:
            raise RuntimeError("VoteNotifier not initialized with bot token")
        return self._bot_token

    async def close(self) -> None:
        """Close every session owned by this notifier."""
        for session in self._sessions.values():
            if not session.closed:
                await session.close()
        self._sessions.clear()
        log.info("VoteNotifier sessions closed")

    def _ensure_session(self) -> aiohttp.ClientSession:
        loop = asyncio.get_running_loop()
        # Drop sessions whose loop has been closed (e.g. a reward thread's
        # asyncio.run loop), so a recycled loop id never reuses a dead session.
        for closed_loop in [loop for loop in self._sessions if loop.is_closed()]:
            del self._sessions[closed_loop]
        session = self._sessions.get(loop)
        if session is None or session.closed:
            session = aiohttp.ClientSession(
                headers={"Authorization": f"Bot {self._get_token()}"},
                timeout=aiohttp.ClientTimeout(total=15),
            )
            self._sessions[loop] = session
        return session

    async def send_notification(
        self,
        user_id: int,
        ball,
        is_new: bool,
        notification_channel_id: int | None,
        site_name: str,
    ) -> bool:
        """Send a vote notification to the configured channel."""
        if not notification_channel_id:
            return False

        session = self._ensure_session()
        message_lines = [
            f"<@{user_id}> voted on {site_name} and received **{ball.ball.country}** `#{ball.pk:0X}`.",
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

        try:
            async with self._semaphore:
                async with session.post(
                    f"https://discord.com/api/v10/channels/{notification_channel_id}/messages",
                    json={"embeds": [embed]},
                ) as resp:
                    if resp.status >= 400:
                        log.warning(
                            "Failed to send %s vote notification (status %s): %s",
                            site_name,
                            resp.status,
                            await resp.text(),
                        )
                        return False
            return True
        except asyncio.CancelledError:
            log.warning("%s vote notification was cancelled", site_name)
            return False
        except Exception:
            log.exception("Failed to send %s vote notification", site_name)
            return False

    async def send_dm(self, user_id: int, content: str, site_name: str) -> bool:
        """Send a DM to the user with their vote reward."""
        session = self._ensure_session()

        try:
            async with self._semaphore:
                async with session.post(
                    "https://discord.com/api/v10/users/@me/channels",
                    json={"recipient_id": str(user_id)},
                ) as resp:
                    if resp.status >= 400:
                        log.warning(
                            "Failed to open DM channel for %s user %s (status %s): %s",
                            site_name,
                            user_id,
                            resp.status,
                            await resp.text(),
                        )
                        return False
                    channel_data = await resp.json()

                async with session.post(
                    f"https://discord.com/api/v10/channels/{channel_data['id']}/messages",
                    json={"content": content},
                ) as resp:
                    if resp.status >= 400:
                        log.warning(
                            "Failed to send %s reward DM to user %s (status %s): %s",
                            site_name,
                            user_id,
                            resp.status,
                            await resp.text(),
                        )
                        return False
            return True
        except asyncio.CancelledError:
            log.warning("%s DM send was cancelled for user %s", site_name, user_id)
            return False
        except Exception:
            log.exception("Unexpected error while sending %s reward DM to user %s", site_name, user_id)
            return False


_vote_notifier: VoteNotifier | None = None


def get_vote_notifier() -> VoteNotifier:
    """Get the global VoteNotifier instance."""
    global _vote_notifier
    if _vote_notifier is None:
        _vote_notifier = VoteNotifier()
    return _vote_notifier


async def init_vote_notifier(bot_token: str) -> VoteNotifier:
    """Initialize the global VoteNotifier with the bot token."""
    notifier = get_vote_notifier()
    notifier.initialize(bot_token)
    return notifier


async def close_vote_notifier() -> None:
    """Close the global VoteNotifier."""
    global _vote_notifier
    if _vote_notifier:
        await _vote_notifier.close()
        _vote_notifier = None
