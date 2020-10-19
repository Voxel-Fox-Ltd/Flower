from discord.ext import tasks
import voxelbotutils as utils


class Analytics(utils.Cog):

    def __init__(self, bot:utils.Bot):
        super().__init__(bot)
        self.flower_count_poster_loop.start()

    def cog_unload(self):
        self.flower_count_poster_loop.cancel()

    @tasks.loop(minutes=1)
    async def flower_count_poster_loop(self):
        async with self.bot.database() as db:
            rows = await db("SELECT plant_nourishment >= 0 AS alive, COUNT(*) FROM plant_levels GROUP BY plant_nourishment >= 0")
        async with self.bot.stats() as stats:
            for row in rows:
                stats.gauge(f"discord.stats.plant_count.{'alive' if row['alive'] else 'dead'}", value=row['count'])


def setup(bot:utils.Bot):
    x = Analytics(bot)
    bot.add_cog(x)
