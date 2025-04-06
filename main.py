from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import requests
import pandas as pd
import ta

TOKEN = os.getenv("TELEGRAM_TOKEN") or "VUL_HIER_JE_TOKEN_IN"

TIMEFRAMES = {
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "1d": "1d"
}

def fetch_trading_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    symbols = [s['symbol'] for s in data['symbols']]
    return symbols

TRADING_PAIRS = fetch_trading_pairs()

def fetch_binance_ohlc(symbol: str, interval: str, limit: int = 100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "_", "_", "_", "_", "_", "_"
    ])
    df["close"] = pd.to_numeric(df["close"])
    df["low"] = pd.to_numeric(df["low"])
    return df

def analyze(symbol: str):
    results = []
    for label, tf in TIMEFRAMES.items():
        df = fetch_binance_ohlc(symbol, tf)
        if df is None or df.empty:
            results.append(f"[{label}] Geen data – mogelijk niet op Binance.")
            continue

        close = df["close"]
        low = df["low"]
        price = close.iloc[-1]
        rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]
        ema9 = ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1]
        ema21 = ta.trend.EMAIndicator(close, window=21).ema_indicator().iloc[-1]

        crossover = "bullish crossover (EMA9 > EMA21)" if ema9 > ema21 else "bearish crossover (EMA9 < EMA21)"
        rsi_desc = f"{rsi:.1f} ({'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutraal'})"

        if rsi < 30 and price > ema21:
            advies = "LONG signaal"
        elif rsi > 70 and price < ema21:
            advies = "SHORT signaal"
        else:
            advies = "Afwachten / Neutraal"

        stop_loss = low.iloc[-1] * 0.99 if advies == "LONG signaal" else low.iloc[-1] * 1.03
        sl_type = "onder" if advies == "LONG signaal" else "boven"
        sl_txt = f"{stop_loss:.2f} ({sl_type} prijs)"

        result = (
            f"[{label}]\n"
            f"- RSI: {rsi_desc}\n"
            f"- {crossover}\n"
            f"- Advies: {advies}\n"
            f"- Stop-loss: {sl_txt}"
        )
        results.append(result)

    return "\n\n".join(results)

async def analyse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Gebruik: /analyse <coin> (bijv. BTC of BTCUSDT)")
        return
    coin = context.args[0].upper()
    if len(coin) <= 4:
        potential_symbol = coin + "USDT"
        if potential_symbol in TRADING_PAIRS:
            coin = potential_symbol
        else:
            await update.message.reply_text(f"Geen handelsparen gevonden voor {coin}. Controleer de ticker en probeer opnieuw.")
            return
    elif coin not in TRADING_PAIRS:
        await update.message.reply_text(f"Geen handelsparen gevonden voor {coin}. Controleer de ticker en probeer opnieuw.")
        return

    await update.message.reply_text(f"Analyse voor {coin} bezig...")
    try:
        resultaat = analyze(coin)
        await update.message.reply_text(f"Analyse voor {coin}:\n\n{resultaat}")
    except Exception as e:
        await update.message.reply_text(f"Fout bij analyse: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welkom bij Spongebot! Gebruik /analyse <coin>, /ping of /hulp.")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pong!")

async def hulp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Beschikbare commando's:\n"
        "/analyse <coin> - Technische analyse van een coin\n"
        "/ping - Check of de bot leeft\n"
        "/start - Startbericht\n"
        "/hulp - Dit hulpbericht"
    )
    await update.message.reply_text(help_text)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("analyse", analyse))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("hulp", hulp))
    print("[INFO] Spongebot TA Advanced gestart...")
    app.run_polling()
