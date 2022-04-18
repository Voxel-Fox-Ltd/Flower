from __future__ import annotations

from discord.ext import tasks, vbu


class PlantAnalytics(vbu.Cog):

    def __init__(self, bot: vbu.Bot):
        super().__init__(bot)
        self.flower_count_poster_loop.start()

    def cog_unload(self):
        self.flower_count_poster_loop.cancel()

    @tasks.loop(minutes=1)
    async def flower_count_poster_loop(self):
        async with vbu.Database() as db:
            rows = await db("SELECT plant_nourishment >= 0 AS alive, COUNT(*) FROM plant_levels GROUP BY plant_nourishment >= 0")
        async with vbu.Stats() as stats:
            for row in rows:
                stats.gauge(f"discord.stats.plant_count.{'alive' if row['alive'] else 'dead'}", value=row['count'])

    @flower_count_poster_loop.before_loop
    async def before_flower_count_poster_loop(self):
        await self.bot.wait_until_ready()


def setup(bot: vbu.Bot):
    x = PlantAnalytics(bot)
    bot.add_cog(x)
