import base64
from datetime import datetime as dt

from aiohttp.web import HTTPFound, Request, RouteTableDef, json_response
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
@template("flowers.j2")
@webutils.requires_login()
@webutils.add_discord_arguments()
async def flowers(request:Request):
    """
    Show the users their flowers.
    """

    session = await aiohttp_session.get_session(request)
    async with request.app['database']() as db:
        user_rows = await db("SELECT * FROM user_settings WHERE user_id=ANY($1::BIGINT[]) ORDER BY user_id DESC LIMIT 1", [session['user_id'], 0])
        plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1", session['user_id'])
    plants = [dict(i) for i in plant_rows]

    display_utils = request.app['bots']['bot'].get_cog("PlantDisplayUtils")
    for data in plants:
        plant_display_dict = display_utils.get_display_data(data, user_id=session['user_id'])
        display_data = display_utils.get_plant_image(**plant_display_dict)
        cropped_display_data = display_utils.crop_image_to_content(display_data)
        image_bytes = display_utils.image_to_bytes(cropped_display_data)
        data['image_data'] = base64.b64encode(image_bytes.read()).decode()

    return {
        'user': dict(user_rows[0]),
        'plants': plants,
    }
