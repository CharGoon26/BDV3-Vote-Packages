from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

try:
    from topgg_notifier.models import TopGGConfig
except Exception:  # pragma: no cover - optional package wiring
    TopGGConfig = None  # type: ignore[assignment]

try:
    from discordlist_notifier.models import DiscordGGConfig
except Exception:  # pragma: no cover - optional package wiring
    DiscordGGConfig = None  # type: ignore[assignment]

try:
    from discordbotlist_notifier.models import DiscordBotListConfig
except Exception:  # pragma: no cover - optional package wiring
    DiscordBotListConfig = None  # type: ignore[assignment]

try:
    from botlistme_notifier.models import BotListMeConfig
except Exception:  # pragma: no cover - optional package wiring
    BotListMeConfig = None  # type: ignore[assignment]


@dataclass(frozen=True)
class VoteSource:
    label: str
    url: str
    button_label: str


class VoteLinkView(discord.ui.View):
    def __init__(self, vote_sources: list[VoteSource]):
        super().__init__(timeout=None)
        for source in vote_sources[:5]:
            self.add_item(discord.ui.Button(label=source.button_label, url=source.url))


class Vote(commands.Cog):
    """Show every configured vote link in one place."""

    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    def _clean_url(self, value: str | None) -> str:
        return value.strip() if value else ""

    async def _resolve_topgg_url(self) -> str:
        if TopGGConfig is not None:
            config = await TopGGConfig.objects.afirst()
            if config:
                vote_url = self._clean_url(config.get_vote_url())
                if vote_url:
                    return vote_url

        env_vote_url = self._clean_url(os.environ.get("TOPGG_VOTE_URL"))
        if env_vote_url:
            return env_vote_url

        bot_id = self._clean_url(os.environ.get("TOPGG_BOT_ID"))
        if bot_id:
            return f"https://top.gg/bot/{bot_id}/vote"

        return ""

    async def _resolve_discordlist_url(self) -> str:
        if DiscordGGConfig is not None:
            config = await DiscordGGConfig.objects.afirst()
            if config:
                vote_url = self._clean_url(config.vote_url)
                if vote_url:
                    return vote_url

        return self._clean_url(os.environ.get("DISCORDLIST_VOTE_URL"))

    async def _resolve_discordbotlist_url(self) -> str:
        if DiscordBotListConfig is not None:
            config = await DiscordBotListConfig.objects.afirst()
            if config:
                vote_url = self._clean_url(config.vote_url)
                if vote_url:
                    return vote_url

        return self._clean_url(os.environ.get("DISCORDBOTLIST_VOTE_URL"))

    async def _resolve_botlistme_url(self) -> str:
        if BotListMeConfig is not None:
            config = await BotListMeConfig.objects.afirst()
            if config:
                vote_url = self._clean_url(config.vote_url)
                if vote_url:
                    return vote_url

        return self._clean_url(os.environ.get("BOTLISTME_VOTE_URL"))

    async def _get_vote_sources(self) -> list[VoteSource]:
        sources: list[VoteSource] = []

        topgg_url = await self._resolve_topgg_url()
        if topgg_url:
            sources.append(VoteSource(label="Top.gg", url=topgg_url, button_label="Vote on Top.gg"))

        discordlist_url = await self._resolve_discordlist_url()
        if discordlist_url:
            sources.append(
                VoteSource(label="DiscordList", url=discordlist_url, button_label="Vote on DiscordList")
            )

        discordbotlist_url = await self._resolve_discordbotlist_url()
        if discordbotlist_url:
            sources.append(
                VoteSource(
                    label="DiscordBotList",
                    url=discordbotlist_url,
                    button_label="Vote on DiscordBotList",
                )
            )

        botlistme_url = await self._resolve_botlistme_url()
        if botlistme_url:
            sources.append(VoteSource(label="BotList.me", url=botlistme_url, button_label="Vote on BotList.me"))

        return sources

    @app_commands.command(name="vote")
    @app_commands.guild_only()
    async def vote(self, interaction: discord.Interaction["BallsDexBot"]):
        vote_sources = await self._get_vote_sources()
        embed = discord.Embed(
            title="Vote Rewards",
            description=(
                "Vote on any configured site to receive **1 random card!**\n"
                "Keep your DMs open so the reward message can reach you."
            ),
            color=discord.Color.blurple(),
        )

        if vote_sources:
            lines = [f"• [{source.label}]({source.url})" for source in vote_sources]
            embed.add_field(name="Available Vote Links", value="\n".join(lines), inline=False)
            embed.set_footer(text="Only sites with saved vote links are shown.")
            view = VoteLinkView(vote_sources)
        else:
            embed.add_field(
                name="Available Vote Links",
                value="No vote links are configured yet. Ask your admin to fill them in.",
                inline=False,
            )
            embed.set_footer(text="The /vote command will update automatically once links are added.")
            view = None

        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)


async def setup(bot: "BallsDexBot"):
    await bot.add_cog(Vote(bot))
