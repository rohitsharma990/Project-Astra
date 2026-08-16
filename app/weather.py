import os
from typing import Any, Dict

import requests
from requests import RequestException, Timeout
from . import ui

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        load_dotenv()
except ImportError:
    pass

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")


def _format_weather_response(data: Dict[str, Any]) -> None:
    location = data.get("location")
    current = data.get("current")
    if not isinstance(location, dict) or not isinstance(current, dict):
        ui.error("Weather service returned incomplete weather information.")
        return

    try:
        name = location["name"]
        region = location.get("region", "")
        country = location.get("country", "")
        temperature = current["temp_c"]
        condition = current["condition"]["text"]
        humidity = current["humidity"]
        wind_kph = current["wind_kph"]
    except (KeyError, TypeError):
        ui.error("Weather service returned malformed weather details.")
        return

    print("ASTRA WEATHER")
    print("--------------------------")
    print(f"📍 {name}, {region}, {country}")
    print(f"🌡 Temperature : {temperature}°C")
    print(f"☁ Condition   : {condition}")
    print(f"💧 Humidity    : {humidity}%")
    print(f"💨 Wind Speed  : {wind_kph} km/h")
    ui.assistant_message(
        f"The weather in {name} is {temperature} degrees Celsius with {condition}."
    )


def get_weather(city: str) -> None:
    if not WEATHER_API_KEY:
        ui.error("Weather API key is not configured. Set WEATHER_API_KEY in .env.")
        return

    city = city.strip()
    if not city:
        ui.error("Please tell me the city for weather information.")
        return

    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Timeout:
        ui.error("Weather service request timed out. Please try again later.")
        return
    except RequestException as err:
        ui.error(f"Weather service request failed: {err}")
        return

    try:
        data = response.json()
    except ValueError:
        ui.error("Weather service returned invalid data.")
        return

    if not isinstance(data, dict):
        ui.error("Weather service returned unexpected data.")
        return

    if "error" in data:
        error_info = data["error"]
        if isinstance(error_info, dict):
            ui.error(error_info.get("message", "City not found."))
        else:
            ui.error("City not found.")
        return

    _format_weather_response(data)
