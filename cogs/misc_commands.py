import asyncio

import discord
from discord.ext import commands

from cogs import utils


class MiscCommands(utils.Cog):

    @commands.command(aliases=['git', 'code'], cls=utils.Command)
    @utils.checks.is_config_set('command_data', 'github')
    @commands.bot_has_permissions(send_messages=True)
    async def github(self, ctx:utils.Context):
        """Sends the GitHub Repository link"""

        await ctx.send(f"<{self.bot.config['command_data']['github']}>")

    @commands.command(aliases=['support', 'guild'], cls=utils.Command)
    @utils.checks.is_config_set('command_data', 'guild_invite')
    @commands.bot_has_permissions(send_messages=True)
    async def server(self, ctx:utils.Context):
        """Gives the invite to the support server"""

        await ctx.send(f"<{self.bot.config['command_data']['guild_invite']}>")

    @commands.command(aliases=['patreon'], cls=utils.Command)
    @utils.checks.is_config_set('command_data', 'patreon')
    @commands.bot_has_permissions(send_messages=True)
    async def donate(self, ctx:utils.Context):
        """Gives you the bot's creator's Patreon"""

        await ctx.send(f"<{self.bot.config['command_data']['patreon']}>")

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @utils.checks.is_config_set('command_data', 'invite_command_enabled')
    async def invite(self, ctx:utils.Context):
        """Gives you the bot's invite link"""

        await ctx.send(f"<{self.bot.get_invite_link(send_messages=True, embed_links=True, attach_files=True)}>")

    @commands.command(cls=utils.Command)
    @commands.bot_has_permissions(send_messages=True)
    @utils.checks.is_config_set('command_data', 'vote_command_enabled')
    async def vote(self, ctx:utils.Context):
        """Gives you a link to vote for the bot"""

        bot_user_id = self.bot.config.get('oauth', {}).get('client_id', None) or self.bot.user.id
        await ctx.send(f"<https://top.gg/bot/{bot_user_id}/vote>")

    @commands.command(cls=utils.Command)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    @utils.checks.is_config_set('command_data', 'echo_command_enabled')
    async def echo(self, ctx:utils.Context, *, content:str):
        """Echos the given content into the channel"""

        await ctx.send(content, allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False))

    @commands.command(aliases=['status'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @utils.checks.is_config_set('command_data', 'stats_command_enabled')
    async def stats(self, ctx:utils.Context):
        """Gives you the stats for the bot"""

        # Get creator info
        creator_id = self.bot.config["owners"][0]
        creator = self.bot.get_user(creator_id) or await self.bot.fetch_user(creator_id)

        # Make embed
        embed = utils.Embed(colour=0x1e90ff)
        embed.set_footer(str(self.bot.user), icon_url=self.bot.user.avatar_url)
        embed.add_field("Creator", f"{creator!s}\n{creator_id}")
        embed.add_field("Library", f"Discord.py {discord.__version__}")
        if self.bot.shard_count != len(self.bot.shard_ids):
            embed.add_field("Approximate Guild Count", int((len(self.bot.guilds) / len(self.bot.shard_ids)) * self.bot.shard_count))
        else:
            embed.add_field("Guild Count", len(self.bot.guilds))
        embed.add_field("Shard Count", self.bot.shard_count)
        embed.add_field("Average WS Latency", f"{(self.bot.latency * 1000):.2f}ms")
        embed.add_field("Coroutines", f"{len([i for i in asyncio.Task.all_tasks() if not i.done()])} running, {len(asyncio.Task.all_tasks())} total.")
        if self.bot.config.get("topgg_token"):
            params = {"fields": "points,monthlyPoints"}
            headers = {"Authorization": self.bot.config['topgg_token']}
            async with self.bot.session.get(f"https://top.gg/api/bots/{self.bot.user.id}", params=params, headers=headers) as r:
                try:
                    data = await r.json()
                except Exception:
                    data = {}
            if "points" in data and "monthlyPoints" in data:
                embed.add_field("Top.gg Points", f"{data['points']} ({data['monthlyPoints']} this month)")

        # Send it out wew let's go
        await ctx.send(embed=embed)


def setup(bot:utils.Bot):
    x = MiscCommands(bot)
    bot.add_cog(x)
