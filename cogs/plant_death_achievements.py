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
    async def update_plant_death_count(
            db: vbu.Database,
            row: utils.types.PlantLevelsRow) -> None:
        """
        Update the plant's death count.
        """

        await db.call(
            """
            INSERT INTO
                plant_achievement_counts
                (
                    user_id,
                    plant_type,
                    plant_death_count
                )
            VALUES
                (
                    $1,
                    $2,
                    1
                )
            ON CONFLICT
                (user_id, plant_type)
            DO UPDATE
            SET
                plant_death_count = plant_death_count + excluded.plant_death_count
            """,
            row['user_id'], row['plant_type'],
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
            dead_plants = await self.kill_plants(db)

            # Add counter for plant dying
            for row in dead_plants:
                await self.update_plant_death_count(db, row)

            # Update max plant lifetime
            await self.update_max_plant_lifetime(db)

    @plant_death_timeout_loop.before_loop
    async def before_plant_death_timeout_loop(self):
        await self.bot.wait_until_ready()


def setup(bot: utils.types.Bot):
    x = PlantDeathTimeout(bot)
    bot.add_cog(x)
