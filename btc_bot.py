import ccxt
import pandas as pd
import numpy as np
import os
import time

# ENV VARS
api_key = os.environ['API_KEY']
api_secret = os.environ['API_SECRET']

symbol = 'BTC/USDT:USDT'
lot_size = 0.002
leverage = 200
risk_reward = 3
timeframe = '15m'

exchange = ccxt.delta({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})
exchange.set_leverage(leverage, symbol)

def fetch_data():
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
    df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    return df

def calc_indicators(df):
    df['hl2'] = (df['high'] + df['low']) / 2
    df['atr'] = df['high'].rolling(19).max() - df['low'].rolling(19).min()
    df['atr'] = df['atr'].ewm(alpha=1/19).mean()
    df['upper'] = df['hl2'] + 5 * df['atr']
    df['lower'] = df['hl2'] - 5 * df['atr']
    df['supertrend'] = True
    for i in range(1, len(df)):
        if df['close'][i] > df['upper'][i-1]:
            df.at[i, 'supertrend'] = True
        elif df['close'][i] < df['lower'][i-1]:
            df.at[i, 'supertrend'] = False
        else:
            df.at[i, 'supertrend'] = df.at[i-1, 'supertrend']
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['cumvol'] = df['volume'].cumsum()
    df['cumvol_price'] = (df['hl2'] * df['volume']).cumsum()
    df['vwap'] = df['cumvol_price'] / df['cumvol']
    return df

def place_order(side, price):
    if side == "buy":
        exchange.create_limit_buy_order(symbol, lot_size, price)
    else:
        exchange.create_limit_sell_order(symbol, lot_size, price)
    print(f"{side.upper()} order placed at {price}")

while True:
    try:
        df = fetch_data()
        df = calc_indicators(df)
        last = df.iloc[-1]
        entry = last['close']
        side = None

        if last['supertrend'] and last['rsi'] < 70 and entry > last['vwap']:
            side = 'buy'
            sl = df.iloc[-1]['lower']
            tp = entry + (entry - sl) * risk_reward
        elif not last['supertrend'] and last['rsi'] > 30 and entry < last['vwap']:
            side = 'sell'
            sl = df.iloc[-1]['upper']
            tp = entry - (sl - entry) * risk_reward

        if side:
            place_order(side, entry)
            print(f"{side.upper()} @ {entry:.2f} | SL: {sl:.2f} | TP: {tp:.2f}")
        else:
            print("No signal")

        time.sleep(60)

    except Exception as e:
        print("ERROR:", str(e))
        time.sleep(60)
