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


def _weather_api_key() -> str:
    """Read the key at call time so .env changes apply without a restart."""
    return os.getenv("WEATHER_API_KEY", "").strip()


def fetch_weather(city: str) -> Dict[str, Any]:
    """Fetch current weather and return structured data.

    Raises:
        RuntimeError: when WEATHER_API_KEY is not configured (clean,
            configuration-required failure — weather is never fabricated).
        ValueError: when the city is empty or the service returns bad data.
    """
    api_key = _weather_api_key()
    if not api_key:
        raise RuntimeError(
            "Weather API key is not configured. Set WEATHER_API_KEY in .env."
        )

    city = str(city or "").strip()
    if not city:
        raise ValueError("Please tell me the city for weather information.")

    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={city}"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Timeout as err:
        raise RuntimeError("Weather service request timed out. Please try again later.") from err
    except RequestException as err:
        raise RuntimeError(f"Weather service request failed: {err}") from err

    try:
        data = response.json()
    except ValueError as err:
        raise ValueError("Weather service returned invalid data.") from err

    if not isinstance(data, dict):
        raise ValueError("Weather service returned unexpected data.")

    if "error" in data:
        error_info = data["error"]
        message = (
            error_info.get("message", "City not found.")
            if isinstance(error_info, dict)
            else "City not found."
        )
        raise ValueError(f"Weather service error: {message}")

    location = data.get("location")
    current = data.get("current")
    if not isinstance(location, dict) or not isinstance(current, dict):
        raise ValueError("Weather service returned incomplete weather information.")

    try:
        name = location["name"]
        region = location.get("region", "")
        country = location.get("country", "")
        temperature = current["temp_c"]
        condition = current["condition"]["text"]
        humidity = current["humidity"]
        wind_kph = current["wind_kph"]
    except (KeyError, TypeError) as err:
        raise ValueError("Weather service returned malformed weather details.") from err

    summary = (
        f"The weather in {name} is {temperature} degrees Celsius with {condition}."
    )
    return {
        "city": name,
        "region": region,
        "country": country,
        "temperature_c": temperature,
        "condition": condition,
        "humidity": humidity,
        "wind_kph": wind_kph,
        "summary": summary,
    }


def _format_weather_response(data: Dict[str, Any]) -> None:
    print("ASTRA WEATHER")
    print("--------------------------")
    print(f"📍 {data['city']}, {data['region']}, {data['country']}")
    print(f"🌡 Temperature : {data['temperature_c']}°C")
    print(f"☁ Condition   : {data['condition']}")
    print(f"💧 Humidity    : {data['humidity']}%")
    print(f"💨 Wind Speed  : {data['wind_kph']} km/h")
    ui.assistant_message(data["summary"])


def get_weather(city: str) -> None:
    """Interactive weather lookup used by the command parser."""
    if not _weather_api_key():
        ui.error("Weather API key is not configured. Set WEATHER_API_KEY in .env.")
        return

    if not str(city or "").strip():
        ui.error("Please tell me the city for weather information.")
        return

    try:
        data = fetch_weather(city)
    except RuntimeError as err:
        ui.error(str(err))
        return
    except ValueError as err:
        ui.error(str(err))
        return

    _format_weather_response(data)