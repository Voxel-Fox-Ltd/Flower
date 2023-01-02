import collections
from datetime import timedelta

from discord.ext import vbu, tasks

from cogs import utils


class PlantDeathTimeout(vbu.Cog[utils.types.Bot]):

    def __init__(self, bot):
        super().__init__(bot)
        self.plant_death_timeout_loop.start()

    def cog_unload(self):
        self.plant_death_timeout_loop.stop()

    @staticmethod
    async def kill_plants(
            db: vbu.Database) -> list[utils.types.PlantLevelsRow]:
        """
        Kill any dead plants in the database.
        """

        return await db.call(
            """
            UPDATE
                plant_levels
            SET
                plant_nourishment = -plant_levels.plant_nourishment
            WHERE
                plant_nourishment > 0
            AND
                last_water_time + $1 < TIMEZONE('UTC', NOW())
            AND
                immortal = FALSE
            RETURNING
                *
            """,
            utils.constants.DEATH_TIMEOUT,
            type=utils.types.PlantLevelsRow,
        )

    @staticmethod
    async def update_max_plant_lifetime(
            db: vbu.Database):
        """
        Set the maximum plant lifetime.
        """

        await db.call(
            """
            INSERT INTO
                user_achievement_counts
                (
                    user_id,
                    max_plant_lifetime
                )
            (
                SELECT
                    user_id,
                    MAX(TIMEZONE('UTC', NOW()) - plant_adoption_time)
                FROM
                    plant_levels
                WHERE
                    plant_levels.plant_nourishment > 0
                AND
                    immortal=FALSE
                GROUP BY
                    user_id
            )
            ON CONFLICT
                (user_id)
            DO UPDATE
            SET
                max_plant_lifetime = GREATEST(
                    user_achievement_counts.max_plant_lifetime,
                    excluded.max_plant_lifetime
                )
            WHERE
                user_achievement_counts.user_id = excluded.user_id
            """,
        )

    @tasks.loop(minutes=1)
    async def plant_death_timeout_loop(self):
        """
        Loop to see if we should kill off any plants that
        may have been timed out.
        """

        async with vbu.Database() as db:

            # Kill any dead plants
            new_dead_plants = await self.kill_plants(db)

            # Update plant death count
            user_death_count: dict[int, int] = collections.defaultdict(int)
            for plant in new_dead_plants:
                user_death_count[plant['user_id']] += 1
            for user_id, death_count in user_death_count.items():
                await utils.achievements.update_achievement_count(
                    db,
                    user_id,
                    utils.achievements.Achievement.deaths,
                    death_count,
                )

            # Update max plant lifetime
            await self.update_max_plant_lifetime(db)

    @plant_death_timeout_loop.before_loop
    async def before_plant_death_timeout_loop(self):
        await self.bot.wait_until_ready()


def setup(bot: utils.types.Bot):
    x = PlantDeathTimeout(bot)
    bot.add_cog(x)
