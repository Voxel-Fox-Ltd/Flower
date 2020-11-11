import contextlib
import copy
import io
import json
import textwrap
import traceback

import discord
from discord.ext import commands

from cogs import utils


class OwnerOnly(utils.Cog, command_attrs={'hidden': True}):
    """Handles commands that only the owner should be able to run"""

    @commands.command(aliases=['pm', 'dm'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def message(self, ctx:utils.Context, user_id:utils.converters.UserID, *, content:str):
        """PMs a user the given content"""

        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        try:
            await user.send(content)
        except discord.Forbidden:
            return await ctx.send("Couldn't send them a DM.")
        except AttributeError:
            return await ctx.send("That person doesn't exist.")
        await ctx.okay()

    def _cleanup_code(self, content):
        """Automatically removes code blocks from the code."""

        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            if content[-4] == '\n':
                return '\n'.join(content.split('\n')[1:-1])
            return '\n'.join(content.split('\n')[1:]).rstrip('`')

        # remove `foo`
        return content.strip('` \n')

    @commands.command(aliases=['evall'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def ev(self, ctx:utils.Context, *, content:str):
        """Evaluates some Python code

        Gracefully stolen from Rapptz ->
        https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/admin.py#L72-L117"""

        # Make the environment
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'self': self,
        }
        env.update(globals())

        # Make code and output string
        content = self._cleanup_code(content)
        code = f'async def func():\n{textwrap.indent(content, "  ")}'

        # Make the function into existence
        stdout = io.StringIO()
        try:
            exec(code, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        # Grab the function we just made and run it
        func = env['func']
        try:
            # Shove stdout into StringIO
            with contextlib.redirect_stdout(stdout):
                ret = await func()
        except Exception:
            # Oh no it caused an error
            stdout_value = stdout.getvalue() or None
            await ctx.send(f'```py\n{stdout_value}\n{traceback.format_exc()}\n```')
        else:
            # Oh no it didn't cause an error
            stdout_value = stdout.getvalue() or None

            # Give reaction just to show that it ran
            await ctx.message.add_reaction("\N{OK HAND SIGN}")

            # If the function returned nothing
            if ret is None:
                # It might have printed something
                if stdout_value is not None:
                    await ctx.send(f'```py\n{stdout_value}\n```')
                return

            # If the function did return a value
            result_raw = stdout_value or ret  # What's returned from the function
            result = str(result_raw)  # The result as a string
            if result_raw is None:
                return
            text = f'```py\n{result}\n```'
            if type(result_raw) == dict:
                try:
                    result = json.dumps(result_raw, indent=4)
                except Exception:
                    pass
                else:
                    text = f'```json\n{result}\n```'
            if len(text) > 2000:
                await ctx.send(file=discord.File(io.StringIO(result), filename='ev.txt'))
            else:
                await ctx.send(text)

    @commands.command(aliases=['rld'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reload(self, ctx:utils.Context, *cog_name:str):
        """Unloads and reloads a cog from the bot"""

        cog_name = 'cogs.' + '_'.join([i for i in cog_name])

        try:
            self.bot.load_extension(cog_name)
        except commands.ExtensionAlreadyLoaded:
            try:
                # self.bot.unload_extension(cog_name)
                # self.bot.load_extension(cog_name)
                self.bot.reload_extension(cog_name)
            except Exception:
                await ctx.send('```py\n' + traceback.format_exc() + '```')
                return
        except Exception:
            await ctx.send('```py\n' + traceback.format_exc() + '```')
            return
        await ctx.send('Cog reloaded.')

    @commands.command(cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def runsql(self, ctx:utils.Context, *, sql:str):
        """Runs a line of SQL into the sparcli database"""

        # Get the data we asked for
        async with self.bot.database() as db:
            rows = await db(sql.format(guild=ctx.guild.id, author=ctx.author.id, channel=ctx.channel.id))
        if not rows:
            return await ctx.send("No content.")

        # Set up some metadata for us to format things nicely
        headers = list(rows[0].keys())
        column_widths = {i: len(i) for i in headers}
        lines = []

        # See how long our lines are
        for row in rows:
            for header in headers:
                column_widths[header] = max([column_widths[header], len(str(row[header]))])

        # Work out our rows
        for row in rows:
            working = ""
            for header in headers:
                working += format(str(row[header]), f" <{column_widths[header]}") + "|"
            lines.append(working[:-1])

        # Add on our headers
        header_working = ""
        spacer_working = ""
        for header in headers:
            header_working += format(header, f" <{column_widths[header]}") + "|"
            spacer_working += "-" * column_widths[header] + "|"
        lines.insert(0, spacer_working[:-1])
        lines.insert(0, header_working[:-1])

        # Send it out
        string_output = '\n'.join(lines)
        try:
            await ctx.send(f"```\n{string_output}```")
        except discord.HTTPException:
            file = discord.File(io.StringIO(string_output), filename="runsql.txt")
            await ctx.send(file=file)

    @commands.group(cls=utils.Group)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def botuser(self, ctx:utils.Context):
        """A parent command for the bot user configuration section"""

        pass

    @botuser.command(aliases=['username'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def name(self, ctx:utils.Context, *, username:str):
        """Lets you set the username for the bot account"""

        if len(username) > 32:
            return await ctx.send('That username is too long.')
        await self.bot.user.edit(username=username)
        await ctx.send('Done.')

    @botuser.command(aliases=['photo', 'image', 'avatar'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def picture(self, ctx:utils.Context, *, image_url:str=None):
        """Lets you set the profile picture of the bot"""

        if image_url is None:
            try:
                image_url = ctx.message.attachments[0].url
            except IndexError:
                return await ctx.send("You need to provide an image.")

        async with self.bot.session.get(image_url) as r:
            image_content = await r.read()
        await self.bot.user.edit(avatar=image_content)
        await ctx.send('Done.')

    @botuser.command(aliases=['game'], cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def activity(self, ctx:utils.Context, activity_type:str, *, name:str=None):
        """Changes the activity of the bot"""

        if name:
            activity = discord.Activity(name=name, type=getattr(discord.ActivityType, activity_type.lower()))
        else:
            return await self.bot.set_default_presence()
        await self.bot.change_presence(activity=activity, status=self.bot.guilds[0].me.status)

    @botuser.command(cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def status(self, ctx:utils.Context, status:str):
        """Changes the online status of the bot"""

        status_o = getattr(discord.Status, status.lower())
        await self.bot.change_presence(activity=self.bot.guilds[0].me.activity, status=status_o)

    @commands.command(cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def sudo(self, ctx, who:discord.User, *, command: str):
        """Run a command as another user optionally in another channel."""

        msg = copy.copy(ctx.message)
        msg.author = ctx.guild.get_member(who.id) or who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        await self.bot.invoke(new_ctx)

    @commands.command(cls=utils.Command)
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    async def addreaction(self, ctx, message:discord.Message, reaction:str):
        """Adds a reaction to a message"""

        await message.add_reaction(reaction)
        await ctx.message.add_reaction("\N{OK HAND SIGN}")


def setup(bot:utils.Bot):
    x = OwnerOnly(bot)
    bot.add_cog(x)
