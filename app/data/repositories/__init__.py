"""Repository implementations for DB-backed persistence."""

from app.data.repositories.analyst_reports import AnalystReportRepository
from app.data.repositories.daily_prices import DailyPriceRepository
from app.data.repositories.decision_logs import DecisionLogRepository
from app.data.repositories.holdings import HoldingRepository
from app.data.repositories.holding_checks import HoldingCheckRepository
from app.data.repositories.job_runs import JobRunRepository
from app.data.repositories.market_cap_rankings import MarketCapRankingRepository
from app.data.repositories.market_regimes import MarketRegimeRepository
from app.data.repositories.news_items import NewsItemRepository
from app.data.repositories.notification_logs import NotificationLogRepository
from app.data.repositories.recommendations import (
    RecommendationRepository,
    RecommendationResultRepository,
    RecommendationRunRepository,
)
from app.data.repositories.report_consensus_snapshots import (
    ReportConsensusSnapshotRepository,
)
from app.data.repositories.report_score_logs import ReportScoreLogRepository
from app.data.repositories.report_signal_events import ReportSignalEventRepository
from app.data.repositories.report_themes import ReportThemeRepository
from app.data.repositories.snapshots import DataSnapshotRepository
from app.data.repositories.stock_indicators import StockIndicatorRepository
from app.data.repositories.stocks import StockRepository
from app.data.repositories.stock_universes import (
    StockUniverseMemberRepository,
    StockUniverseRepository,
)
from app.data.repositories.theme_stock_mappings import ThemeStockMappingRepository

__all__ = [
    "AnalystReportRepository",
    "DataSnapshotRepository",
    "DailyPriceRepository",
    "DecisionLogRepository",
    "HoldingRepository",
    "HoldingCheckRepository",
    "JobRunRepository",
    "MarketCapRankingRepository",
    "MarketRegimeRepository",
    "NewsItemRepository",
    "NotificationLogRepository",
    "RecommendationRepository",
    "RecommendationResultRepository",
    "RecommendationRunRepository",
    "ReportConsensusSnapshotRepository",
    "ReportScoreLogRepository",
    "ReportSignalEventRepository",
    "ReportThemeRepository",
    "StockIndicatorRepository",
    "StockRepository",
    "StockUniverseMemberRepository",
    "StockUniverseRepository",
    "ThemeStockMappingRepository",
]
