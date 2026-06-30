async def setup(bot):
    from .cog import setup as ext_setup

    await ext_setup(bot)
