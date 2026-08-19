import pandas as pd


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    loss = loss.replace(0, 0.00001)
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def detect_whale_activity(
    df: pd.DataFrame, volume_multiplier: float = 2.5
) -> dict:
    if df.empty or len(df) < 15:
        return {
            "detected": False,
            "score": 0,
            "close_price": 0,
            "vol_ratio": 0,
            "rsi": 0,
            "price_change_pct": 0,
            "reasons": "Yetersiz Veri",
            "target_1pct": 0,
            "target_2pct": 0,
        }

    latest = df.iloc[-1]
    lookback = min(20, len(df) - 1)
    prev_bars = df.iloc[-(lookback + 1):-1]

    avg_vol = prev_bars["Volume"].mean()
    curr_vol = latest["Volume"]
    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0

    price_change_pct = ((latest["Close"] - latest["Open"]) / latest["Open"]) * 100

    df["EMA_50"] = df["Close"].ewm(span=min(50, len(df)), adjust=False).mean()
    df["RSI"] = calculate_rsi(df["Close"], 14)

    latest_rsi = df["RSI"].iloc[-1] if "RSI" in df else 50
    latest_ema = df["EMA_50"].iloc[-1] if "EMA_50" in df else latest["Close"]
    close_price = latest["Close"]

    score = 0
    reasons = []

    if vol_ratio >= volume_multiplier:
        score += 30
        reasons.append(f"Hacim {round(vol_ratio, 1)}x")

    if price_change_pct > 0:
        score += 20
        reasons.append("Pozitif Mum")

    if close_price >= latest_ema:
        score += 20
        reasons.append("Trend Yukarı (EMA+)")

    if 40 <= latest_rsi <= 70:
        score += 15
        reasons.append(f"RSI İdeal ({round(latest_rsi, 1)})")

    candle_range = latest["High"] - latest["Low"]
    if candle_range > 0 and (latest["Close"] - latest["Low"]) / candle_range > 0.65:
        score += 15
        reasons.append("Güçlü Kapanış")

    is_high_probability = score >= 70

    return {
        "detected": is_high_probability,
        "score": score,
        "close_price": round(close_price, 2),
        "vol_ratio": round(vol_ratio, 2),
        "rsi": round(latest_rsi, 1) if pd.notna(latest_rsi) else 0,
        "price_change_pct": round(price_change_pct, 2),
        "reasons": " | ".join(reasons) if reasons else "Kriter Karşılanmadı",
        "target_1pct": round(close_price * 1.01, 2),
        "target_2pct": round(close_price * 1.02, 2),
    }