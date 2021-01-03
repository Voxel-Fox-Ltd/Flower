from aiohttp.web import HTTPFound, Request, RouteTableDef
from voxelbotutils import web as webutils
import aiohttp_session
import discord
from aiohttp_jinja2 import template


routes = RouteTableDef()


@routes.get("/")
@template("index.j2")
@webutils.add_discord_arguments()
async def index(request:Request):
    """
    Handle the index page for the website.
    """

    return {}


@routes.get("/flowers")
@template("index.j2")
@webutils.requires_login()
@webutils.add_discord_arguments()
async def flowers(request:Request):
    """
    Show the users their flowers.
    """

    session = await aiohttp_session.get_session(request)
    async with request.app['database']() as db:
        rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", session['user_id'])
    return {
        'plants': [dict(i) for i in rows]
    }
