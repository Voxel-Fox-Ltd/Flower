from aiohttp.web import HTTPFound, Request, RouteTableDef, Response, json_response
from voxelbotutils import web as webutils
import aiohttp_session


routes = RouteTableDef()


@routes.get('/login_processor')
async def login_processor(request:Request):
    """
    Page the discord login redirects the user to when successfully logged in with Discord.
    """

    await webutils.process_discord_login(request)
    session = await aiohttp_session.get_session(request)
    return HTTPFound(location=session.pop('redirect_on_login', '/'))


@routes.get('/login')
async def login(request:Request):
    """
    Direct the user to the bot's Oauth login page.
    """

    return HTTPFound(location=webutils.get_discord_login_url(request, "/login_processor"))


@routes.get('/logout')
async def logout(request:Request):
    """
    Destroy the user's login session.
    """

    session = await aiohttp_session.get_session(request)
    session.invalidate()
    return HTTPFound(location='/')


@routes.post('/water_plant')
async def water_plant(request:Request):
    """
    Water a plant for the user.
    """

    session = await aiohttp_session.get_session(request)
    if session.get("logged_in", False) is False:
        return Response(status=401)
    post_data = await request.json()
    care_utils = request.app['bots']['bot'].get_cog("PlantCareCommands")
    item = await care_utils.water_plant_backend(session['user_id'], post_data['plant_name'])
    if not item['success']:
        return json_response(item, status=400)
    return json_response(item, status=200)


@routes.post('/delete_plant')
async def delete_plant(request:Request):
    """
    Delete a plant for the user.
    """

    session = await aiohttp_session.get_session(request)
    if session.get("logged_in", False) is False:
        return Response(status=401)
    post_data = await request.json()
    care_utils = request.app['bots']['bot'].get_cog("PlantCareCommands")
    item = await care_utils.delete_plant_backend(session['user_id'], post_data['plant_name'])
    if not item:
        return json_response({"success": False}, status=400)
    return json_response({"success": True}, status=200)


@routes.post('/revive_plant')
async def revive_plant(request:Request):
    """
    Revive a plant for the user.
    """

    session = await aiohttp_session.get_session(request)
    if session.get("logged_in", False) is False:
        return Response(status=401)
    post_data = await request.json()
    care_utils = request.app['bots']['bot'].get_cog("PlantCareCommands")
    response, success = await care_utils.revive_plant_backend(session['user_id'], post_data['plant_name'])
    if not success:
        return json_response({"success": success}, status=400)
    return json_response({"success": success}, status=200)
