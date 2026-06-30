from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


class TopggNotifier(commands.Cog):
    """Webhook-only Top.gg notifier package."""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(TopggNotifier(bot))
