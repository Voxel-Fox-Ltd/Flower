import base64
import random

from aiohttp.web import Request, RouteTableDef
from voxelbotutils import web as webutils
import aiohttp_session
from aiohttp_jinja2 import template


routes = RouteTableDef()


@routes.get("/")
@template("index.j2")
@webutils.add_discord_arguments()
async def index(request:Request):
    """
    Handle the index page for the website.
    """

    bot = request.app['bots']['bot']
    invite_link = bot.get_invite_link(**{i: True for i in bot.config['command_data']['invite_command_permissions']})
    return {'invite_link': invite_link}


@routes.get("/flowers")
@template("flowers.j2")
@webutils.requires_login()
@webutils.add_discord_arguments()
async def flowers(request:Request):
    """
    Show the users their flowers.
    """

    session = await aiohttp_session.get_session(request)
    try:
        user_id = request.query.get('user_id', session['user_id'])
        user_id = int(user_id)
        if user_id != session['user_id'] and session['user_id'] not in request.app['bots']['bot'].config['owner_ids']:
            raise ValueError()
    except ValueError:
        user_id = session['user_id']

    async with request.app['database']() as db:
        user_rows = await db("SELECT * FROM user_settings WHERE user_id=ANY($1::BIGINT[]) ORDER BY user_id DESC LIMIT 1", [user_id, 0])
        if user_id:
            plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 ORDER BY plant_name ASC", user_id)
        else:
            plant_rows = await db("SELECT * FROM plant_levels ORDER BY RANDOM() ASC LIMIT 100")
    plants = [dict(i) for i in plant_rows]

    display_utils = request.app['bots']['bot'].get_cog("PlantDisplayUtils")
    for data in plants:
        plant_display_dict = display_utils.get_display_data(data, user_id=data['user_id'])
        display_data = display_utils.get_plant_image(**plant_display_dict)
        cropped_display_data = display_utils.crop_image_to_content(display_data)
        image_bytes = display_utils.image_to_bytes(cropped_display_data)
        data['image_data'] = base64.b64encode(image_bytes.read()).decode()

    return {
        'user': dict(user_rows[0]),
        'plants': plants,
    }


generated_herbiary = None
generated_herbiary_lifetime = 0


@routes.get("/herbiary")
@template("herbiary.j2")
@webutils.add_discord_arguments()
async def herbiary(request:Request):
    """
    Show the user the entire plant list.
    """

    global generated_herbiary
    global generated_herbiary_lifetime

    if generated_herbiary is None or generated_herbiary_lifetime >= 10:
        output = list(request.app['bots']['bot'].plants.copy().values())
        display_utils = request.app['bots']['bot'].get_cog("PlantDisplayUtils")
        for plant in output:
            plant_data = {'plant_type': plant.name, 'plant_nourishment': plant.max_nourishment_level, 'original_owner_id': random.randint(0, 359)}
            plant_display_dict = display_utils.get_display_data(plant_data)
            display_data = display_utils.get_plant_image(**plant_display_dict)
            cropped_display_data = display_utils.crop_image_to_content(display_data)
            image_bytes = display_utils.image_to_bytes(cropped_display_data)
            plant.image_data = base64.b64encode(image_bytes.read()).decode()
        generated_herbiary = output
        generated_herbiary_lifetime = -1
    generated_herbiary_lifetime += 1

    return {
        'plants': generated_herbiary,
    }
