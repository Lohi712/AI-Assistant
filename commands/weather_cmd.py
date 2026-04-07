"""
Weather command for VEGA AI Assistant.

Fetches current weather data from OpenWeatherMap API.
"""

import requests

from commands.base import BaseCommand
from utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "http://api.openweathermap.org/data/2.5/weather"


class WeatherCommand(BaseCommand):
    """Get current weather for a city."""

    priority = 30

    @property
    def triggers(self) -> list[str]:
        return ["weather"]

    def execute(self, query: str, assistant) -> None:
        api_key = assistant.settings.openweather_api_key
        if not api_key:
            assistant.speech.speak(
                "Weather service is not configured. Please set your OpenWeatherMap API key."
            )
            return

        # Try to extract city from query first
        city_name = self._extract_city(query)

        if not city_name:
            assistant.speech.speak("Which city's weather would you like to know?")
            city_name = assistant.speech.listen().lower()
            if city_name in ("none", ""):
                assistant.speech.speak("I didn't catch the city name.")
                return

        assistant.speech.speak(f"Checking the weather in {city_name}.")

        try:
            response = requests.get(
                BASE_URL,
                params={"appid": api_key, "q": city_name, "units": "metric"},
                timeout=10,
            )
            data = response.json()

            if data.get("cod") == 404 or data.get("cod") == "404":
                assistant.speech.speak(
                    f"Sorry, I couldn't find weather data for {city_name}."
                )
                return

            main = data["main"]
            weather_desc = data["weather"][0]["description"]
            temp = main["temp"]
            feels_like = main.get("feels_like", temp)
            humidity = main.get("humidity", "N/A")

            report = (
                f"The temperature in {city_name} is {temp}°C, "
                f"feels like {feels_like}°C, with {weather_desc}. "
                f"Humidity is {humidity}%."
            )
            print(f"\n🌤️  {report}\n")
            assistant.speech.speak(report)

        except requests.RequestException as e:
            logger.error("Weather API error: %s", e)
            assistant.speech.speak("Sorry, I couldn't fetch the weather details.")

    @staticmethod
    def _extract_city(query: str) -> str:
        """Try to extract city name from the query itself."""
        # Handle patterns like "weather in delhi" or "weather of mumbai"
        for preposition in ("in ", "of ", "for ", "at "):
            if preposition in query:
                parts = query.split(preposition, 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return ""
