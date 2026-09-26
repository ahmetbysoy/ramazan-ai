"""
FastAPI Server & Real-Time Data Streaming for Binance Analytics & MEV Bot.
Serves interactive mobile dashboard and REST analytics API.
"""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.aggregator import MarketDataAggregator

# Root directory of bot
BASE_DIR = Path(__file__).resolve().parent

# Global Aggregator Instance
aggregator = MarketDataAggregator(symbol="btcusdt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start ingestion loop
    await aggregator.start()
    yield
    # Cleanup
    await aggregator.stop()


app = FastAPI(
    title="Binance Autonomous Analytics & MEV Bot",
    description="Real-time multi-timeframe predictions, depth wall trade setups, and MEV frontrunning radar",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/status")
async def get_status():
    """Returns the latest calculated analytics snapshot."""
    return aggregator.compute_full_snapshot()


@app.get("/api/orderbook")
async def get_orderbook():
    """Returns the latest orderbook depth walls and trade setup."""
    snapshot = aggregator.compute_full_snapshot()
    return snapshot.get("orderbook", {})


@app.get("/api/mev")
async def get_mev():
    """Returns the latest MEV sandwich and frontrunning metrics."""
    snapshot = aggregator.compute_full_snapshot()
    return snapshot.get("mevAnalytics", {})


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the mobile-first cyberpunk trading dashboard."""
    html_file = BASE_DIR / "static" / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard Loading...</h1>", status_code=200)


def run_app(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn
    uvicorn.run("src.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run_app()
