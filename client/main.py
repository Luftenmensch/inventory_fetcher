import asyncio
import logging
import re
import struct
import sys
import urllib.parse
from collections import Counter

import aiohttp
import ujson
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode

dp = Dispatcher()


def load_settings() -> dict:
    fname = 'settings.json'
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            return ujson.load(f)
    except FileNotFoundError:
        default_settings = {
            'bot_token': ''
        }
        with open(fname, 'w', encoding='utf-8') as f:
            ujson.dump(default_settings, f, indent=4)
        input('Нужно указать bot token в настройках!')
        exit()


def get_steam_id(trade_url: str) -> str:
    query_string = urllib.parse.urlparse(trade_url).query
    args = urllib.parse.parse_qs(query_string)
    first_bytes = int(args['partner'][0]).to_bytes(4, byteorder='big')
    last_bytes = 0x1100001.to_bytes(4, byteorder='big')
    return str(struct.unpack('>Q', last_bytes + first_bytes)[0])


def format_message(steam_id: str, response: dict) -> str:
    msg = steam_id
    updated = response['updated']
    if updated == 0:
        msg += ', обновлено только что'
    else:
        msg += f', обновлено {updated} секунд назад'
    data = response['data']
    if 'error' in data:
        return data['error']
    items = data['items']
    prices = {}
    for item in items:
        item_prices = item['prices']
        for k, v in item_prices.items():
            if k in prices:
                if v:
                    prices[k].append(v)
            else:
                if v:
                    prices[k] = [v]
    prices_text = '\n'
    total_items = len(items)
    for provider, all_prices in prices.items():
        total_price = sum(all_prices) / 100
        prices_text += f'{provider.capitalize()}: ${total_price:.2f}'
        prices_text += f' (Без цен: {int(total_items - len(all_prices))})\n' if len(
            all_prices) < total_items else '\n'
    if items:
        msg += prices_text
    else:
        msg += 'Инвентарь пуст'
    return msg


async def fetch_steam_id(profile_url: str) -> str:
    if Counter(profile_url)['/'] > 4:
        profile_url = '/'.join(profile_url.split('/')[:5])
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=profile_url) as response:
                data = await response.text()
                return data.split('"steamid":"')[1].split('"')[0]
    except ConnectionError:
        return {'error': 'Ошибка при обработке запроса'}
    except:
        return {'error': 'Ошибка при получении Steam ID'}


async def get_inventory_price(steam_id: str) -> dict:
    params = {
        'steam_id': steam_id
    }
    url = 'http://server:8000/get_data'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params) as response:
                return await response.json()
    except ConnectionError:
        return {'error': 'Ошибка при обработке запроса'}
    except:
        return {'error': 'Некорретный ответ от сервера'}


@dp.message()
async def echo(message: types.Message) -> None:
    trade_url_pattern = re.compile(
        r'^https?:\/\/steamcommunity.com\/tradeoffer\/new\/\?partner=\d{8,12}&token=[A-Za-z_\d]{6,10}$'
    )
    steam_id_pattern = re.compile(
        r'^\d{17}$'
    )
    profile_url_pattern = re.compile(
        r'https:\/\/steamcommunity\.com\/(id|profiles)\/[a-zA-Z0-9]+\/?'
    )
    if message.text == "/start":
        await message.answer('Здравствуйте, для использования бота вставьте ссылку на ваш профиль или id steam')
        return
    elif trade_url_pattern.match(message.text):
        await message.answer('Получил ссылку на обмен, обрабатываю запрос')
        steam_id = get_steam_id(message.text)
    elif steam_id_pattern.match(message.text):
        await message.answer('Получил Steam ID, обрабатываю запрос')
        steam_id = message.text
    elif profile_url_pattern.match(message.text):
        await message.answer('Получил ссылку на профиль, обрабатываю запрос')
        steam_id = await fetch_steam_id(message.text)
        if 'error' in steam_id:
            await message.answer(steam_id['error'])
            return
    else:
        await message.answer('Неверные входные параметры!\nОтправьте Steam ID, ссылку на профиль или ссылку на обмен')
        return
    response = await get_inventory_price(steam_id)
    if 'error' in response:
        response_message = response['error']
    else:
        response_message = format_message(steam_id, response)
    await message.answer(response_message)


async def main() -> None:
    bot = Bot(bot_token, parse_mode=ParseMode.HTML)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    settings = load_settings()
    bot_token = settings['bot_token']
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
