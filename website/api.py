import base64
from datetime import datetime as dt

from aiohttp.web import Request, RouteTableDef, json_response


routes = RouteTableDef()


@routes.get('/api/v1/get_plant')
async def get_plant(request:Request):
    """
    Get a specific plant's information (including a b64-encoded image) from the database.
    """

    # Get the user ID
    try:
        user_id = request.query.get('user_id')
        assert user_id is not None
        user_id = int(user_id)
    except (ValueError, AssertionError):
        return json_response({"error": "Invalid user ID provided."}, status=400)

    # Get the plant name
    try:
        plant_name = request.query.get('plant_name')
        assert plant_name
    except (ValueError, AssertionError):
        return json_response({"error": "No plant name provided"}, status=400)

    # Grab database information
    async with request.app['database']() as db:
        plant_rows = await db("SELECT * FROM plant_levels WHERE user_id=$1 AND LOWER(plant_name)=LOWER($2) ORDER BY plant_name ASC", user_id, plant_name)
        if not plant_rows:
            return json_response({"error": "", "data": {}})

    # Grab the plant image
    data = [dict(i) for i in plant_rows][0]
    display_utils = request.app['bots']['bot'].get_cog("PlantDisplayUtils")
    plant_display_dict = display_utils.get_display_data(data, user_id=user_id)
    display_data = display_utils.get_plant_image(**plant_display_dict)
    cropped_display_data = display_utils.crop_image_to_content(display_data)
    image_bytes = display_utils.image_to_bytes(cropped_display_data)
    data['image_data'] = base64.b64encode(image_bytes.read()).decode()

    return json_response({"error": "", "data": {x: y if not isinstance(y, dt) else y.timestamp() for x, y in data.items()}})
