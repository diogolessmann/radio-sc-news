"""
weather.py — Clima em tempo real para as cidades do Norte de SC
Usa OpenWeatherMap API (gratuita)
"""
import os
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

WEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '')

CITIES = [
    {'name': 'Schroeder',      'query': 'Schroeder,SC,BR',       'emoji': '🏡'},
    {'name': 'Jaraguá do Sul', 'query': 'Jaragua do Sul,SC,BR',  'emoji': '🏭'},
    {'name': 'Guaramirim',     'query': 'Guaramirim,SC,BR',      'emoji': '🌿'},
    {'name': 'Joinville',      'query': 'Joinville,SC,BR',       'emoji': '🏙️'},
]

WEATHER_ICONS = {
    'Clear':        '☀️',
    'Clouds':       '☁️',
    'Rain':         '🌧️',
    'Drizzle':      '🌦️',
    'Thunderstorm': '⛈️',
    'Snow':         '❄️',
    'Mist':         '🌫️',
    'Fog':          '🌫️',
    'Haze':         '🌫️',
}

_cache = {}
_cache_time = {}
CACHE_MINUTES = 30


def _is_cached(city):
    if city not in _cache_time:
        return False
    return datetime.now() - _cache_time[city] < timedelta(minutes=CACHE_MINUTES)


def fetch_city_weather(city_config):
    name = city_config['name']
    if _is_cached(name):
        return _cache[name]

    if not WEATHER_API_KEY:
        return None

    try:
        url = 'https://api.openweathermap.org/data/2.5/weather'
        params = {
            'q': city_config['query'],
            'appid': WEATHER_API_KEY,
            'units': 'metric',
            'lang': 'pt_br',
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            logger.warning(f"OpenWeather erro {resp.status_code} para {name}")
            return None

        data = resp.json()
        main = data.get('weather', [{}])[0]
        result = {
            'city': name,
            'emoji': city_config['emoji'],
            'temp': round(data['main']['temp']),
            'feels_like': round(data['main']['feels_like']),
            'humidity': data['main']['humidity'],
            'description': main.get('description', ''),
            'icon': WEATHER_ICONS.get(main.get('main', ''), '🌡️'),
            'wind': round(data.get('wind', {}).get('speed', 0) * 3.6),  # m/s → km/h
        }
        _cache[name] = result
        _cache_time[name] = datetime.now()
        return result
    except Exception as e:
        logger.error(f"Erro ao buscar clima de {name}: {e}")
        return None


def fetch_all_weather():
    results = []
    for city in CITIES:
        data = fetch_city_weather(city)
        if data:
            results.append(data)
    return results
