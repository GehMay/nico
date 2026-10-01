import requests

from config import WEATHER_CITY

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
IP_GEOLOCATION_URL = "http://ip-api.com/json"

# Códigos de tempo da WMO usados pelo Open-Meteo - versão resumida, só o
# suficiente para uma frase curta e natural.
_WEATHER_CODES = {
    0: "clear sky",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with heavy hail",
}


def _describe_weather_code(code):
    return _WEATHER_CODES.get(code, "unusual weather")


def _detect_city_by_ip():
    response = requests.get(IP_GEOLOCATION_URL, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("status") != "success":
        raise RuntimeError("IP geolocation failed")
    return data["city"], data["lat"], data["lon"]


def _geocode_city(city):
    response = requests.get(GEOCODING_URL, params={"name": city, "count": 1}, timeout=10)
    response.raise_for_status()
    results = response.json().get("results")
    if not results:
        raise RuntimeError(f"Could not find coordinates for '{city}'")
    result = results[0]
    return result["name"], result["latitude"], result["longitude"]


def get_weather_report():
    """Retorna uma frase curta com o clima atual, usando WEATHER_CITY (do
    .env) ou, se vazio, a cidade detectada pelo IP. Levanta uma exceção se
    algo falhar - quem chama decide o que fazer (ex.: cair pra busca web).
    """
    if WEATHER_CITY:
        city, lat, lon = _geocode_city(WEATHER_CITY)
    else:
        city, lat, lon = _detect_city_by_ip()

    response = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "temperature_unit": "celsius",
        },
        timeout=10,
    )
    response.raise_for_status()
    current = response.json()["current_weather"]

    description = _describe_weather_code(current["weathercode"])
    temperature = round(current["temperature"])

    return f"It's currently {temperature} degrees Celsius with {description} in {city}."
