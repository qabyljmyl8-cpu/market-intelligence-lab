from storage.database import Database
from storage.repositories import Repository
from orchestration.schemas import AgentReport, AgentStatus, ConsolidatedReport, DataQualityReport, MarketClassification


def test_sqlite_preference_persistence(tmp_path):
    path = tmp_path / "app.sqlite3"
    repo = Repository(Database(path))
    repo.set_preference("default_asset", "BTC/USDT")
    reopened = Repository(Database(path))
    assert reopened.get_preference("default_asset") == "BTC/USDT"


def test_analysis_and_agent_reports_persist(tmp_path):
    repo = Repository(Database(tmp_path / "analysis.sqlite3"))
    agent = AgentReport(agent_name="technical_market_structure", status=AgentStatus.OK, summary="test report")
    report = ConsolidatedReport(asset="BTC/USDT", timeframe="1h", classification=MarketClassification.INCONCLUSIVE,
        evidence_quality="low", summary="test", alternative_scenario="uncertain", data_quality=DataQualityReport(status=AgentStatus.OK, row_count=10),
        agent_reports={agent.agent_name: agent}, evidence_strength_score=0)
    analysis_id = repo.save_analysis(report)
    history = repo.analysis_history()
    assert history[0]["id"] == analysis_id
    assert repo.get_analysis_json(analysis_id) is not None
    assert repo.get_agent_reports(analysis_id)[0]["agent_name"] == "technical_market_structure"
