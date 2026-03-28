from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime
import json
import os

app = FastAPI()

# 简单内存日志。测试够用；后面再换数据库。
EVENTS = []

SECRET = os.getenv("WEBHOOK_SECRET", "change-me")


def score_signal(data: dict) -> dict:
    score = 0
    reasons = []

    event = str(data.get("event") or "")
    symbol = str(data.get("symbol") or "")
    timeframe = str(data.get("interval") or "")
    close_raw = data.get("close")
    volume_raw = data.get("volume")

    try:
        close = float(close_raw) if close_raw is not None else 0.0
    except (TypeError, ValueError):
        close = 0.0

    try:
        volume = float(volume_raw) if volume_raw is not None else 0.0
    except (TypeError, ValueError):
        volume = 0.0

    if event in {"test", "long_candidate"}:
        score += 30
        reasons.append("Received valid signal")

    if symbol:
        score += 10
        reasons.append("Symbol present")

    if close > 0:
        score += 20
        reasons.append("Price valid")

    if volume > 0:
        score += 20
        reasons.append("Volume valid")

    if timeframe in {"1", "3", "5", "15", "30", "60", "120", "240", "1D", "D", "1W", "W"}:
        score += 10
        reasons.append("Timeframe valid")

    if score >= 80:
        rating = "A"
    elif score >= 60:
        rating = "B"
    else:
        rating = "C"

    return {
        "score": score,
        "rating": rating,
        "reasons": reasons,
    }


@app.get("/")
def home():
    return {"status": "running"}


@app.get("/events")
def list_events():
    return {"count": len(EVENTS), "events": EVENTS[-20:]}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    rows = ""
    for e in reversed(EVENTS[-50:]):
        analysis = e.get("analysis", {})
        rows += f"""
        <tr>
            <td>{e.get('received_at', '')}</td>
            <td>{e.get('symbol', '')}</td>
            <td>{e.get('event', '')}</td>
            <td>{e.get('close', '')}</td>
            <td>{e.get('timeframe', '')}</td>
            <td>{analysis.get('rating', '')}</td>
            <td>{analysis.get('score', '')}</td>
            <td><pre>{json.dumps(e, ensure_ascii=False, indent=2)}</pre></td>
        </tr>
        """
    return f"""
    <html>
    <head>
        <title>TradingView Webhook Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            td, th {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
            th {{ background: #f5f5f5; }}
            pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; }}
        </style>
    </head>
    <body>
        <h1>TradingView Webhook Dashboard</h1>
        <p>Total events: {len(EVENTS)}</p>
        <table>
            <thead>
                <tr>
                    <th>Received At</th>
                    <th>Symbol</th>
                    <th>Event</th>
                    <th>Close</th>
                    <th>Timeframe</th>
                    <th>Rating</th>
                    <th>Score</th>
                    <th>Payload</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </body>
    </html>
    """


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    raw = await request.body()
    text = raw.decode("utf-8")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": "Invalid JSON"}
        )

    # 简单校验，避免别人乱打你的接口
    if data.get("secret") != SECRET:
        return JSONResponse(
            status_code=401,
            content={"ok": False, "error": "Invalid secret"}
        )

    analysis = score_signal(data)

    event = {
        "received_at": datetime.utcnow().isoformat() + "Z",
        "source": data.get("source"),
        "event": data.get("event"),
        "symbol": data.get("symbol"),
        "exchange": data.get("exchange"),
        "timeframe": data.get("interval"),
        "close": data.get("close"),
        "volume": data.get("volume"),
        "tv_time": data.get("time"),
        "analysis": analysis,
        "raw": data,
    }

    EVENTS.append(event)

    return {
        "ok": True,
        "saved": True,
        "symbol": event["symbol"],
        "analysis": analysis,
    }