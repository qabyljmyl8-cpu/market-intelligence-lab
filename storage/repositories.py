"""Persistent repositories for analysis records, preferences, and paper events."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from typing import Any
from orchestration.schemas import ConsolidatedReport
from storage.database import Database

class Repository:
    def __init__(self, database: Database | None = None): self.db = database or Database()

    def save_analysis(self, report: ConsolidatedReport) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute("INSERT INTO analysis_history(created_at,asset,timeframe,classification,evidence_score,report_json) VALUES(?,?,?,?,?,?)",
                (now, report.asset, report.timeframe, report.classification.value, report.evidence_strength_score, report.model_dump_json()))
            analysis_id = int(cursor.lastrowid)
            for name, agent_report in report.agent_reports.items():
                conn.execute("INSERT INTO agent_reports(analysis_id,agent_name,status,report_json) VALUES(?,?,?,?)",
                    (analysis_id, name, agent_report.status.value, agent_report.model_dump_json()))
            return analysis_id

    def analysis_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT id,created_at,asset,timeframe,classification,evidence_score FROM analysis_history ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 500)),)).fetchall()
        return [dict(row) for row in rows]

    def get_analysis_json(self, analysis_id: int) -> str | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT report_json FROM analysis_history WHERE id=?", (int(analysis_id),)).fetchone()
        return row["report_json"] if row else None

    def get_agent_reports(self, analysis_id: int) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT agent_name,status,report_json FROM agent_reports WHERE analysis_id=? ORDER BY id", (int(analysis_id),)).fetchall()
        return [dict(row) for row in rows]

    def set_preference(self, key: str, value: Any) -> None:
        with self.db.transaction() as conn:
            conn.execute("INSERT INTO user_preferences(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                         (str(key), json.dumps(value, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self.db.connection() as conn:
            row = conn.execute("SELECT value FROM user_preferences WHERE key=?", (str(key),)).fetchone()
        if not row: return default
        try: return json.loads(row["value"])
        except (ValueError, TypeError): return default

    def add_paper_event(self, event_type: str, symbol: str | None, side: str | None,
                        quantity: float, price: float, fee: float, cash_delta: float, note: str = "") -> int:
        with self.db.transaction() as conn:
            cursor = conn.execute("INSERT INTO paper_events(created_at,event_type,symbol,side,quantity,price,fee,cash_delta,note) VALUES(?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), event_type, symbol, side, float(quantity), float(price), float(fee), float(cash_delta), str(note)[:500]))
            return int(cursor.lastrowid)

    def paper_events(self) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT * FROM paper_events ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def reset_paper_events(self) -> None:
        with self.db.transaction() as conn: conn.execute("DELETE FROM paper_events")
