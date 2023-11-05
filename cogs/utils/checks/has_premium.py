from discord.ext import commands


__all__ = (
    'DoesNotHavePremium',
    'has_premium',
)


class DoesNotHavePremium(commands.CheckFailure):
    def __init__(self):
        super().__init__(
            "You need to have premium to be able to run this command."
        )


def has_premium():
    """
    A check for whether the user has premium.
    """

    async def predicate(ctx):
        if ctx.original_author_id in ctx.bot.owner_ids:
            return True
        async with ctx.bot.database() as db:
            rows = await db(
                """
                SELECT
                    *
                FROM
                    user_settings
                WHERE
                    user_id = $1
                AND
                (
                        has_premium = true
                    OR
                        premium_expiry_time > TIMEZONE('UTC', NOW())
                )
                """,
                ctx.author.id,
            )
        if rows:
            return True
        raise DoesNotHavePremium()
    return commands.check(predicate)
