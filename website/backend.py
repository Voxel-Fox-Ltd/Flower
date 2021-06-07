from datetime import datetime as dt

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


@routes.post('/webhooks/voxelfox/paypal')
async def purchase_complete(request: Request):
    """
    Handles incomming webhooks from Voxel Fox for the PayPal purchase IPN
    """

    # Get our data
    data = await request.json()
    product_name = data['product_name']
    quantity = data.get('quantity', 0)
    user_id = int(data['discord_user_id'])
    discord_channel_send_text = None
    bot = request.app['bots']['bot']

    # Process exp adds
    if product_name == "Flower 2000 EXP":
        experience = 2000 * quantity
        if data['refund']:
            experience = -experience
        async with request.app['database']() as db:
            await db(
                """INSERT INTO user_settings (user_id, user_experience) VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET
                user_experience=user_settings.user_experience+excluded.user_experience""",
                user_id, experience,
            )

        # Send DMs
        if experience > 0:
            try:
                user = await bot.fetch_user(user_id)
                await user.send(f"Added **{experience:,} exp** to your account!")
            except Exception:
                pass

        # Work out what to send to Discord
        if data['refunded']:
            discord_channel_send_text = f"<@{user_id}> just refunded **{product_name}** x{quantity}."
        else:
            discord_channel_send_text = f"<@{user_id}> just purchased **{product_name}** x{quantity}!"

    # Process subscription
    elif product_name == "Flower Premium":
        expiry_time = data['subscription_expiry_time']
        if expiry_time:
            expiry_time = dt.fromtimestamp(expiry_time)
        async with request.app['database']() as db:
            await db(
                """INSERT INTO user_settings (user_id, has_premium, premium_expiry_time) VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET has_premium=excluded.has_premium,
                premium_expiry_time=excluded.premium_expiry_time""",
                user_id, not bool(expiry_time), expiry_time,
            )

        # Work out what to send to Discord
        if expiry_time:
            discord_channel_send_text = f"<@{user_id}> cancelled their subscription to Flower Premium. It will expire on {expiry_time.strftime('%c')}."
        else:
            discord_channel_send_text = f"<@{user_id}> subscribed to Flower Premium."

    # Send data to channel
    channel_id = request.app['config']['paypal']['notification_channel_id']
    if channel_id and discord_channel_send_text:
        try:
            channel = await bot.fetch_channel(channel_id)
            await channel.send(discord_channel_send_text)
        except Exception:
            pass

    # And done
    return Response(status=200)
