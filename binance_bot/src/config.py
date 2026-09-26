from dataclasses import dataclass, field
from typing import FrozenSet, Dict, Any
import os

@dataclass(frozen=True)
class NetworkConfig:
    """Network parameters and WebSocket endpoints configuration."""
    websocket_url: str = field(
        default_factory=lambda: os.getenv("TRADING_WEBSOCKET_URL", "wss://stream.binance.com:9443/ws")
    )
    rest_api_url: str = field(
        default_factory=lambda: os.getenv("TRADING_REST_API_URL", "https://api.binance.com")
    )
    connection_timeout_seconds: float = 10.0
    heartbeat_interval_seconds: float = 30.0
    max_reconnect_attempts: int = 5
    reconnect_backoff_base_seconds: float = 1.0


@dataclass(frozen=True)
class TradingConfig:
    """Trading constants and parameter configuration."""
    supported_trading_pairs: FrozenSet[str] = field(
        default_factory=lambda: frozenset({"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"})
    )
    default_leverage: int = 1
    max_position_size_usd: float = 10000.0
    order_execution_timeout_seconds: float = 5.0
    slippage_tolerance_pct: float = 0.5


@dataclass(frozen=True)
class AppConfig:
    """Global immutable application configuration containing network and trading parameters."""
    network: NetworkConfig = field(default_factory=NetworkConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a nested dictionary representation."""
        return {
            "network": {
                "websocket_url": self.network.websocket_url,
                "rest_api_url": self.network.rest_api_url,
                "connection_timeout_seconds": self.network.connection_timeout_seconds,
                "heartbeat_interval_seconds": self.network.heartbeat_interval_seconds,
                "max_reconnect_attempts": self.network.max_reconnect_attempts,
                "reconnect_backoff_base_seconds": self.network.reconnect_backoff_base_seconds,
            },
            "trading": {
                "supported_trading_pairs": sorted(list(self.trading.supported_trading_pairs)),
                "default_leverage": self.trading.default_leverage,
                "max_position_size_usd": self.trading.max_position_size_usd,
                "order_execution_timeout_seconds": self.trading.order_execution_timeout_seconds,
                "slippage_tolerance_pct": self.trading.slippage_tolerance_pct,
            }
        }


# Global default configuration instance (immutable)
config = AppConfig()
