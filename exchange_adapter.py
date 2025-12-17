# exchange_adapter.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import ccxt


class ExchangeAdapterError(RuntimeError):
    pass


@dataclass
class ExchangeConfig:
    api_key: Optional[str] = None
    secret: Optional[str] = None
    password: Optional[str] = None  # OKX passphrase
    market_type: str = "spot"        # "spot" or "swap"
    sandbox: bool = False
    enable_rate_limit: bool = True
    timeout_ms: int = 10000


class ExchangeAdapter:
    """
    A thin wrapper around ccxt.okx to isolate exchange-specific behavior.
    """

    def __init__(self, cfg: ExchangeConfig):
        self.cfg = cfg
        self.exchange: Optional[ccxt.okx] = None
        self.last_error: Optional[str] = None

    def initialize_exchange(self) -> ccxt.okx:
        config: Dict[str, Any] = {
            "enableRateLimit": self.cfg.enable_rate_limit,
            "timeout": self.cfg.timeout_ms,
            "options": {
                # defaultType helps disambiguate spot vs swap endpoints when method has no symbol
                "defaultType": self.cfg.market_type,
            },
        }

        # only attach credentials if present (allow read-only mode for public data)
        if self.cfg.api_key:
            config["apiKey"] = self.cfg.api_key
        if self.cfg.secret:
            config["secret"] = self.cfg.secret
        if self.cfg.password:
            config["password"] = self.cfg.password

        ex = ccxt.okx(config)

        # IMPORTANT: sandbox must be first call after creating exchange
        if self.cfg.sandbox:
            ex.set_sandbox_mode(True)

        # warm up markets mapping (optional but helps symbol normalization)
        ex.load_markets()

        self.exchange = ex
        self.last_error = None
        return ex

    def _require_exchange(self) -> ccxt.okx:
        if not self.exchange:
            raise ExchangeAdapterError("Exchange not initialized. Call initialize_exchange() first.")
        return self.exchange

    def normalize_symbol(self, symbol: str) -> str:
        """
        Accepts: BTC/USDT, BTC-USDT, BTCUSDT, BTC-USDT-SWAP
        Produces (best-effort):
          spot: BTC/USDT
          swap: BTC/USDT:USDT
        Note: If you use non-USDT quotes, adjust mapping rules.
        """
        s = symbol.strip().upper()

        # common OKX swap id style
        if s.endswith("-SWAP"):
            s = s.replace("-SWAP", "")

        # BTCUSDT -> BTC/USDT (best-effort)
        if "/" not in s and "-" not in s and s.endswith("USDT") and len(s) > 4:
            base = s[:-4]
            quote = "USDT"
            s = f"{base}/{quote}"

        # BTC-USDT -> BTC/USDT
        if "-" in s and "/" not in s:
            parts = s.split("-")
            if len(parts) >= 2:
                s = f"{parts[0]}/{parts[1]}"

        # swap unified symbol in ccxt is often BASE/QUOTE:SETTLE
        if self.cfg.market_type in ("swap", "future"):
            if ":" not in s:
                # assume USDT-settled if quote is USDT
                if s.endswith("/USDT"):
                    s = s + ":USDT"

        return s

    def _wrap(self, fn, *args, **kwargs):
        try:
            self.last_error = None
            return fn(*args, **kwargs)
        except ccxt.NetworkError as e:
            self.last_error = f"NetworkError: {type(e).__name__}: {e}"
            raise
        except ccxt.ExchangeError as e:
            self.last_error = f"ExchangeError: {type(e).__name__}: {e}"
            raise
        except Exception as e:
            self.last_error = f"UnknownError: {type(e).__name__}: {e}"
            raise

    # --- Unified methods (mirror your engine call sites) ---

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200, since: Optional[int] = None, params: Optional[dict] = None):
        ex = self._require_exchange()
        sym = self.normalize_symbol(symbol)
        return self._wrap(ex.fetch_ohlcv, sym, timeframe=timeframe, since=since, limit=limit, params=params or {})

    def fetch_ticker(self, symbol: str, params: Optional[dict] = None):
        ex = self._require_exchange()
        sym = self.normalize_symbol(symbol)
        return self._wrap(ex.fetch_ticker, sym, params or {})

    def fetch_orderbook(self, symbol: str, limit: Optional[int] = None, params: Optional[dict] = None):
        ex = self._require_exchange()
        sym = self.normalize_symbol(symbol)
        return self._wrap(ex.fetch_order_book, sym, limit, params or {})

    def fetch_balance(self, params: Optional[dict] = None):
        ex = self._require_exchange()
        return self._wrap(ex.fetch_balance, params or {})

    def fetch_positions(self, symbols: Optional[list] = None, params: Optional[dict] = None):
        ex = self._require_exchange()
        # some exchanges behave better when you don't pass symbol; keep it optional
        return self._wrap(ex.fetch_positions, symbols, params or {}) if symbols else self._wrap(ex.fetch_positions, None, params or {})

    def create_order(self, symbol: str, type: str, side: str, amount: float, price: Optional[float] = None, params: Optional[dict] = None):
        ex = self._require_exchange()
        sym = self.normalize_symbol(symbol)
        return self._wrap(ex.create_order, sym, type, side, amount, price, params or {})

    def cancel_order(self, order_id: str, symbol: Optional[str] = None, params: Optional[dict] = None):
        ex = self._require_exchange()
        sym = self.normalize_symbol(symbol) if symbol else None
        return self._wrap(ex.cancel_order, order_id, sym, params or {})
