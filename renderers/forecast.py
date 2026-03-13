import os

from driver import graphics
from PIL import Image

ICON_SIZE = 10
FONT_HEIGHT = 5
DISTANCE_FROM_TOP = 32
DAY_POSITION = DISTANCE_FROM_TOP - FONT_HEIGHT - ICON_SIZE
ICON_POSITION = DISTANCE_FROM_TOP - FONT_HEIGHT - ICON_SIZE
TEMP_POSITION = DISTANCE_FROM_TOP

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "forecast")


def render_forecast(canvas, layout, colors, forecast_days):
    """Render 3-day forecast on the canvas. Returns nothing; draws directly."""
    font_data = layout.font("offday.time")
    font = font_data["font"]
    font_width = font_data["size"]["width"]

    # Colors: use offday.time color for day names, hardcode orange/blue for temps
    day_color = graphics.Color(255, 182, 193)   # light pink
    max_color = graphics.Color(255, 140, 0)      # dark orange
    min_color = graphics.Color(100, 149, 237)    # cornflower blue

    offset = 1
    space_width = canvas.width // 3

    for day in forecast_days[:3]:
        day_name = day["day_name"]
        weather_code = day["weather_code"]
        min_temp = f"{day['temp_min']:.0f}"
        max_temp = f"{day['temp_max']:.0f}"

        # Center calculations
        min_temp_width = len(min_temp) * font_width
        max_temp_width = len(max_temp) * font_width

        temp_x = offset + (space_width - min_temp_width - max_temp_width - 1) // 2 + 1
        max_temp_x = temp_x
        min_temp_x = temp_x + max_temp_width

        icon_x = offset + (space_width - ICON_SIZE) // 2
        day_x = offset + (space_width - 12) // 2 + 1

        # Draw day name
        graphics.DrawText(canvas, font, day_x, DAY_POSITION, day_color, day_name)

        # Draw weather icon
        icon_path = os.path.join(ICON_DIR, f"{weather_code}.png")
        try:
            image = Image.open(icon_path)
            try:
                resample = Image.Resampling.LANCZOS
            except AttributeError:
                resample = Image.ANTIALIAS
            image.thumbnail((ICON_SIZE, ICON_SIZE), resample)
            # Draw icon pixel by pixel (same approach as offday weather icon)
            rgb_image = image.convert("RGBA")
            for x in range(rgb_image.width):
                for y in range(rgb_image.height):
                    pixel = rgb_image.getpixel((x, y))
                    if len(pixel) >= 4 and pixel[3] > 0:
                        canvas.SetPixel(icon_x + x, ICON_POSITION + y, pixel[0], pixel[1], pixel[2])
                    elif len(pixel) == 3:
                        canvas.SetPixel(icon_x + x, ICON_POSITION + y, pixel[0], pixel[1], pixel[2])
        except FileNotFoundError:
            pass

        # Draw temperatures
        graphics.DrawText(canvas, font, max_temp_x, TEMP_POSITION, max_color, max_temp)
        graphics.DrawText(canvas, font, min_temp_x, TEMP_POSITION, min_color, min_temp)

        offset += space_width
        if offset >= canvas.width:
            break
