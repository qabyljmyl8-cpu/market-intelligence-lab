"""Persistent paper-only portfolio simulation; no exchange trading interface."""
from __future__ import annotations
import math
from storage.repositories import Repository

class PaperPortfolio:
    def __init__(self, repository: Repository | None = None, starting_cash: float = 10_000.0):
        if starting_cash <= 0: raise ValueError("starting_cash must be positive")
        self.repository = repository or Repository()
        saved = self.repository.get_preference("paper_starting_cash", None)
        self.starting_cash = float(saved if saved is not None else starting_cash)
        if saved is None: self.repository.set_preference("paper_starting_cash", self.starting_cash)

    def state(self, marks: dict[str, float] | None = None) -> dict:
        marks = marks or {}
        cash = self.starting_cash
        positions: dict[str, dict] = {}
        realized = 0.0
        events = self.repository.paper_events()
        for event in events:
            kind = event["event_type"]
            if kind == "reset": continue
            cash += float(event["cash_delta"])
            symbol = event.get("symbol")
            if not symbol or kind != "trade": continue
            side = str(event["side"]).lower()
            qty, price, fee = float(event["quantity"]), float(event["price"]), float(event["fee"])
            pos = positions.setdefault(symbol, {"quantity": 0.0, "average_cost": 0.0, "realized_pnl": 0.0})
            if side == "buy":
                old_qty = pos["quantity"]
                old_cost = old_qty * pos["average_cost"]
                pos["quantity"] += qty
                pos["average_cost"] = (old_cost + qty * price + fee) / pos["quantity"] if pos["quantity"] else 0.0
            elif side == "sell":
                sale_qty = qty
                if sale_qty > pos["quantity"] + 1e-10:
                    # Stored events should never violate this; expose a consistency failure.
                    raise RuntimeError("Persisted paper events contain a sale exceeding the position.")
                pnl = (price - pos["average_cost"]) * sale_qty - fee
                pos["realized_pnl"] += pnl; realized += pnl
                pos["quantity"] -= sale_qty
                if pos["quantity"] <= 1e-10: pos["quantity"], pos["average_cost"] = 0.0, 0.0
        holdings_value = 0.0
        unrealized = 0.0
        clean_positions = {}
        for symbol, pos in positions.items():
            qty = float(pos["quantity"]); avg = float(pos["average_cost"])
            mark = float(marks.get(symbol, avg))
            if not math.isfinite(mark) or mark <= 0: mark = avg
            market_value = qty * mark
            upnl = qty * (mark - avg)
            holdings_value += market_value; unrealized += upnl
            if qty > 1e-10:
                clean_positions[symbol] = {"quantity": qty, "average_cost": avg, "mark_price": mark,
                    "market_value": market_value, "unrealized_pnl": upnl, "realized_pnl": float(pos["realized_pnl"])}
        equity = cash + holdings_value
        gross_exposure_ratio = holdings_value / equity if equity > 0 else None
        cash_ratio = cash / equity if equity > 0 else None
        curve = self.history_curve(events=events)
        max_dd = float(curve["drawdown"].min()) if len(curve) and "drawdown" in curve else None
        return {"starting_cash": self.starting_cash, "cash": cash, "positions": clean_positions,
                "holdings_value": holdings_value, "equity": equity, "realized_pnl": realized,
                "unrealized_pnl": unrealized, "total_pnl": equity - self.starting_cash,
                "drawdown_from_start": (equity / self.starting_cash - 1.0) if self.starting_cash else None,
                "gross_exposure_ratio": gross_exposure_ratio, "cash_ratio": cash_ratio,
                "max_drawdown": max_dd, "events": events}

    def execute(self, side: str, symbol: str, quantity: float, price: float, fee_rate: float = 0.001) -> int:
        side = side.lower().strip(); symbol = symbol.upper().strip()
        if side not in {"buy", "sell"}: raise ValueError("Paper side must be buy or sell.")
        if not symbol or len(symbol) > 30: raise ValueError("Invalid symbol.")
        if not math.isfinite(quantity) or quantity <= 0: raise ValueError("Quantity must be a finite positive number.")
        if not math.isfinite(price) or price <= 0: raise ValueError("Price must be a finite positive number.")
        if not math.isfinite(fee_rate) or not 0 <= fee_rate < 1: raise ValueError("Fee rate must be between 0 and 1.")
        current = self.state()
        notional = quantity * price
        fee = notional * fee_rate
        if side == "buy":
            cash_delta = -(notional + fee)
            if current["cash"] + cash_delta < -1e-8: raise ValueError("Insufficient simulated cash for this purchase and fee.")
        else:
            position = current["positions"].get(symbol)
            if not position or quantity > position["quantity"] + 1e-10: raise ValueError("Cannot simulate a sale larger than the current paper position.")
            cash_delta = notional - fee
        return self.repository.add_paper_event("trade", symbol, side, quantity, price, fee, cash_delta,
                                               "PAPER ONLY — no exchange order was sent.")

    def reset(self, confirmed: bool, starting_cash: float | None = None) -> None:
        if not confirmed: raise ValueError("Reset requires explicit confirmation.")
        if starting_cash is not None and (not math.isfinite(starting_cash) or starting_cash <= 0):
            raise ValueError("Starting cash must be a finite positive number.")
        self.repository.reset_paper_events()
        if starting_cash is not None:
            self.starting_cash = float(starting_cash)
            self.repository.set_preference("paper_starting_cash", self.starting_cash)

    def history_curve(self, events: list[dict] | None = None):
        """Equity/drawdown snapshots at paper transactions using last transaction marks.

        Prices for assets without a new transaction are held at their last transaction
        price (or average cost before their first recorded price). This is not a live
        mark-to-market series.
        """
        import pandas as pd
        events = self.repository.paper_events() if events is None else events
        cash = self.starting_cash
        positions: dict[str, dict[str, float]] = {}
        marks: dict[str, float] = {}
        rows = [{"timestamp": None, "cash": cash, "holdings_value": 0.0, "equity": cash,
                 "realized_pnl": 0.0, "unrealized_pnl": 0.0, "drawdown": 0.0}]
        realized = 0.0
        for event in events:
            if event["event_type"] != "trade": continue
            cash += float(event["cash_delta"])
            symbol = event.get("symbol")
            if not symbol: continue
            side = str(event["side"]).lower()
            qty, price, fee = float(event["quantity"]), float(event["price"]), float(event["fee"])
            position = positions.setdefault(symbol, {"quantity": 0.0, "average_cost": 0.0})
            if side == "buy":
                old_qty = position["quantity"]
                old_cost = old_qty * position["average_cost"]
                position["quantity"] += qty
                position["average_cost"] = (old_cost + qty * price + fee) / position["quantity"] if position["quantity"] else 0.0
            elif side == "sell":
                sale_qty = min(qty, position["quantity"])
                realized += (price - position["average_cost"]) * sale_qty - fee
                position["quantity"] -= sale_qty
                if position["quantity"] <= 1e-10:
                    position["quantity"], position["average_cost"] = 0.0, 0.0
            marks[symbol] = price
            holdings = sum(p["quantity"] * marks.get(sym, p["average_cost"]) for sym, p in positions.items())
            unrealized = sum(p["quantity"] * (marks.get(sym, p["average_cost"]) - p["average_cost"]) for sym, p in positions.items())
            equity = cash + holdings
            prior_peak = max(r["equity"] for r in rows)
            drawdown = equity / prior_peak - 1.0 if prior_peak > 0 else 0.0
            rows.append({"timestamp": event["created_at"], "cash": cash, "holdings_value": holdings,
                         "equity": equity, "realized_pnl": realized, "unrealized_pnl": unrealized,
                         "drawdown": drawdown})
        return pd.DataFrame(rows)

    def history(self) -> list[dict]:
        return [e for e in self.repository.paper_events() if e["event_type"] == "trade"]
