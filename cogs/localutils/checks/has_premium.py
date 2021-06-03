from discord.ext import commands


def has_premium():
    async def predicate(ctx):
        return await commands.is_owner().predicate(ctx)
    return commands.check(predicate)
