import asyncio
import aiohttp
import ccxt.async_support as ccxt_async
import time
from datetime import datetime
import random

# ==================== НАСТРОЙКИ ====================
TELEGRAM_BOT_TOKEN = '8837723330:AAGexcQ0emLY4CCqZAxBzzjCkELIJkYIhb0'
TELEGRAM_CHAT_ID = '7624706962'

TARGET_COINS = 150
TRADE_USDT = 100
MIN_SPREAD = 0.3
MIN_PROFIT = 0.5
SCAN_PAUSE = 90

BLACKLIST = ['USDT/USDT', 'USDC/USDT', 'BUSD/USDT']

EXCHANGES = {
    'bybit': {'fee': 0.1, 'withdraw': 1.0},
    'kucoin': {'fee': 0.1, 'withdraw': 1.0},
    'gateio': {'fee': 0.2, 'withdraw': 1.0},
    'mexc': {'fee': 0.0, 'withdraw': 1.0},
    'bitget': {'fee': 0.1, 'withdraw': 1.0},
}

def get_time():
    return datetime.utcnow().strftime('%H:%M:%S')

# ==================== TELEGRAM ====================
async def send_msg(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})
            return r.status == 200
    except:
        return False

# ==================== ЛОГИКА ====================
async def get_coins():
    for name in ['bybit', 'kucoin', 'mexc']:
        try:
            ex = getattr(ccxt_async, name)({'enableRateLimit': True})
            await ex.load_markets()
            coins = [s for s in ex.symbols if '/USDT' in s and s not in BLACKLIST]
            await ex.close()
            random.shuffle(coins)
            print(f"✅ {name}: loaded {len(coins[:TARGET_COINS])} coins")
            return coins[:TARGET_COINS]
        except Exception as e:
            print(f"⚠️ {name} error: {str(e)[:40]}")
    return []

async def check_price(ex_id, symbol):
    try:
        ex = getattr(ccxt_async, ex_id)({'timeout': 5000})
        ob = await ex.fetch_order_book(symbol, limit=1)
        await ex.close()
        if ob['bids'] and ob['asks']:
            return {'buy': ob['asks'][0][0], 'sell': ob['bids'][0][0]}
    except:
        return None

async def scan_coin(symbol):
    tasks = {eid: check_price(eid, symbol) for eid in EXCHANGES}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    prices = {}
    for (eid, _), res in zip(tasks.items(), results):
        if isinstance(res, dict) and res.get('buy'):
            prices[eid] = res
    
    best = None
    max_p = 0
    ids = list(prices.keys())
    
    for b in ids:
        for s in ids:
            if b == s: continue
            bp, sp = prices[b]['buy'], prices[s]['sell']
            spread = ((sp - bp) / bp) * 100
            if spread < MIN_SPREAD: continue
            
            crypto = TRADE_USDT / bp
            profit = (sp * crypto) - TRADE_USDT - (TRADE_USDT * EXCHANGES[b]['fee']/100) - (sp*crypto * EXCHANGES[s]['fee']/100) - EXCHANGES[b]['withdraw']
            
            if profit > max_p and profit >= MIN_PROFIT:
                max_p = profit
                best = {'sym': symbol, 'b_ex': b, 's_ex': s, 'bp': bp, 'sp': sp, 'spr': spread, 'prof': profit}
    return best

# ==================== ГЛАВНЫЙ ЦИКЛ ====================
async def main():
    print("🚀 BOT STARTED")
    await send_msg(f"🚀 <b>BOT STARTED</b>\nTime: {get_time()}")
    
    cycle = 0
    while True:
        cycle += 1
        t0 = time.time()
        
        coins = await get_coins()
        if not coins:
            await asyncio.sleep(60); continue
            
        print(f"🔄 Cycle #{cycle}: {len(coins)} coins...")
        found = []
        
        # Сканируем по 5 монет параллельно
        for i in range(0, len(coins), 5):
            batch = coins[i:i+5]
            res = await asyncio.gather(*[scan_coin(c) for c in batch], return_exceptions=True)
            found.extend([r for r in res if isinstance(r, dict)])
            await asyncio.sleep(0.1)
            
        dur = time.time() - t0
        
        if found:
            found.sort(key=lambda x: x['prof'], reverse=True)
            msg = f"🔥 <b>CYCLE #{cycle}</b> ({dur:.0f}s)\n\n"
            for i, o in enumerate(found[:3], 1):
                msg += f"{i}. <b>{o['sym']}</b>\n   {o['b_ex'].upper()} ${o['bp']:.4f} -> {o['s_ex'].upper()} ${o['sp']:.4f}\n   {o['spr']:.2f}% | 💰 ${o['prof']:.2f}\n\n"
            await send_msg(msg + f"Time: {get_time()}")
        else:
            print(f"😴 No opportunities ({dur:.0f}s)")
            
        sleep = max(0, SCAN_PAUSE - dur)
        if sleep > 0: await asyncio.sleep(sleep)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
