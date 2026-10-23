import pytest
from storage.database import Database
from storage.repositories import Repository
from backtesting.paper_portfolio import PaperPortfolio


def make_portfolio(tmp_path):
    repo = Repository(Database(tmp_path / "paper.sqlite3"))
    return PaperPortfolio(repo, starting_cash=1000.0)


def test_buy_sell_and_mark_to_market_accounting(tmp_path):
    portfolio = make_portfolio(tmp_path)
    portfolio.execute("buy", "BTC/USDT", 2, 100, 0.001)
    state = portfolio.state({"BTC/USDT": 110})
    assert state["cash"] == pytest.approx(799.8)
    assert state["positions"]["BTC/USDT"]["quantity"] == pytest.approx(2)
    assert state["unrealized_pnl"] == pytest.approx(19.8)
    portfolio.execute("sell", "BTC/USDT", 1, 120, 0.001)
    final = portfolio.state({"BTC/USDT": 110})
    assert final["cash"] == pytest.approx(919.68)
    assert final["realized_pnl"] == pytest.approx(19.78)
    assert final["total_pnl"] == pytest.approx(29.68)


def test_cannot_buy_more_than_simulated_cash(tmp_path):
    portfolio = make_portfolio(tmp_path)
    with pytest.raises(ValueError, match="Insufficient"):
        portfolio.execute("buy", "BTC/USDT", 100, 100, 0.001)


def test_cannot_sell_more_than_paper_position(tmp_path):
    portfolio = make_portfolio(tmp_path)
    with pytest.raises(ValueError, match="larger"):
        portfolio.execute("sell", "BTC/USDT", 0.1, 100)


def test_reset_requires_confirmation_and_clears_history(tmp_path):
    portfolio = make_portfolio(tmp_path)
    portfolio.execute("buy", "ETH/USDT", 1, 100)
    with pytest.raises(ValueError, match="confirmation"):
        portfolio.reset(False)
    portfolio.reset(True)
    assert portfolio.history() == []
    assert portfolio.state()["cash"] == pytest.approx(1000)


def test_paper_portfolio_equity_and_drawdown_history(tmp_path):
    portfolio = make_portfolio(tmp_path)
    portfolio.execute("buy", "BTC/USDT", 2, 100, 0.001)
    portfolio.execute("sell", "BTC/USDT", 1, 90, 0.001)
    curve = portfolio.history_curve()
    assert len(curve) == 3  # initial state plus two simulated events
    assert "equity" in curve and "drawdown" in curve
    assert curve["drawdown"].min() < 0
    assert portfolio.state()["max_drawdown"] == pytest.approx(float(curve["drawdown"].min()))
