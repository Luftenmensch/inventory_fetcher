import time
from urllib.parse import quote

import aiohttp
import redis
import ujson
import uvicorn
from fastapi import FastAPI

app = FastAPI()
redis_client = redis.Redis(host='redis', port=6379, db=0)


def load_settings() -> dict:
    fname = 'settings.json'
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            return ujson.load(f)
    except FileNotFoundError:
        default_settings = {
            'data_ttl': 20
        }
        with open(fname, 'w', encoding='utf-8') as f:
            ujson.dump(default_settings, f, indent=4)
        return default_settings


async def fetch_profile_data(profile_url: str):
    url = 'https://api.pricempire.com/v3/inventory/public'
    params = {
        'query': profile_url
    }
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url=url, params=params) as response:
                return await response.json()
    except:
        return {'error': 'Ошибка при запросе статуса профиля'}


async def fetch_inventory_data(profile_url: str):
    profile_data = await fetch_profile_data(profile_url)
    if 'error' in profile_data:
        return profile_data
    url = 'https://api.pricempire.com/v3/inventory/public/items'
    cur_time = int(time.time() * 1000)
    params = {
        'query': profile_data['steam64Id'],
        'provider': 'buff',
        'force': quote(ujson.dumps({'isTrusted': True, '_vts': cur_time})),
        'appId': 730
    }
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url=url, params=params) as response:
                return await response.json()
    except:
        return {'error': 'Ошибка при запросе инвентаря'}


@app.get('/get_data')
async def get_data(steam_id: str):
    cached_data = redis_client.get(steam_id)
    if cached_data:
        updated = round(data_ttl - redis_client.ttl(steam_id))
        return {
            'data': ujson.loads(cached_data.decode('utf-8')),
            'updated': updated
        }
    else:
        api_data = await fetch_inventory_data(steam_id)
        if 'error' in api_data:
            return api_data
        redis_client.setex(steam_id, data_ttl, ujson.dumps(api_data))
        updated = round(data_ttl - redis_client.ttl(steam_id))
        return {
            'data': api_data,
            'updated': updated
        }


if __name__ == "__main__":
    settings = load_settings()
    data_ttl = int(float(settings['data_ttl']) * 60)
    uvicorn.run(app, host='0.0.0.0', port=8000)
