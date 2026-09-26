import pytest
import dataclasses
from src.config import config, AppConfig, NetworkConfig, TradingConfig


def test_config_loads_defaults():
    """Test that default WebSocket endpoints and trading pairs load without errors."""
    assert config is not None
    assert isinstance(config, AppConfig)
    assert isinstance(config.network, NetworkConfig)
    assert isinstance(config.trading, TradingConfig)

    assert config.network.websocket_url == "wss://stream.binance.com:9443/ws"
    assert config.network.rest_api_url == "https://api.binance.com"
    assert isinstance(config.trading.supported_trading_pairs, frozenset)
    assert "BTCUSDT" in config.trading.supported_trading_pairs
    assert "ETHUSDT" in config.trading.supported_trading_pairs


def test_config_immutability():
    """Verify that configuration data structures are immutable (frozen dataclasses)."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.network.connection_timeout_seconds = 20.0

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.trading.default_leverage = 5

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.network = NetworkConfig(websocket_url="wss://new.url")


def test_config_to_dict():
    """Test the serialization dictionary method of AppConfig."""
    d = config.to_dict()
    assert isinstance(d, dict)
    assert "network" in d
    assert "trading" in d
    assert d["network"]["websocket_url"] == "wss://stream.binance.com:9443/ws"
    assert isinstance(d["trading"]["supported_trading_pairs"], list)
    assert "BTCUSDT" in d["trading"]["supported_trading_pairs"]


def test_env_override(monkeypatch):
    """Test environment variable overrides for network parameters."""
    monkeypatch.setenv("TRADING_WEBSOCKET_URL", "wss://custom.websocket.endpoint/ws")
    monkeypatch.setenv("TRADING_REST_API_URL", "https://custom.api.com")

    custom_network = NetworkConfig()
    assert custom_network.websocket_url == "wss://custom.websocket.endpoint/ws"
    assert custom_network.rest_api_url == "https://custom.api.com"
