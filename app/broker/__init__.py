"""Broker boundary.

Phase B (v0.14) introduces ``SimulationBroker`` as the FIRST concrete
implementation of ``BrokerInterface``. It is an internal paper-trading
simulator -- it never imports or calls KIS / DART / RSS / any external
HTTP client.

Phase B (v0.16) introduces ``KisOrderClientInterface`` ABC and
``FakeKisOrderTransport`` as the skeleton for real KIS order integration.

Phase B (v1.0) introduces ``HttpxKisOrderTransport`` as the FIRST concrete
real-HTTP implementation of ``KisOrderClientInterface``. It is wired into
``RealOrderExecutor`` real-path execution only in v1.0 Phase C, and
remains structurally unreachable while ``REAL_ORDER_DRY_RUN`` /
``KIS_ORDER_ENABLED`` / ``REAL_TRADING_ENABLED`` paranoid defaults hold.
All tests cover this transport via ``respx`` mocks — zero real KIS calls.
"""

from app.broker.fill_sync_service import FillSyncResult, FillSyncService
from app.broker.real_order_executor import ExecutorResult, RealOrderExecutor
from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisCancelResult,
    KisFillStatusResult,
    KisOrderClientInterface,
    KisOrderRequest,
    KisOrderResult,
    mask_sensitive_order_payload,
)
from app.broker.kis_order_transport_real import (
    CancelClassification,
    FillClassification,
    HttpxKisOrderTransport,
    PlaceClassification,
)
from app.broker.simulation_broker import (
    ExecutePendingResult,
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
    SubmitResult,
)


__all__ = [
    # v0.16 Phase D — Real order executor + fill sync (dry-run only)
    "ExecutorResult",
    "FillSyncResult",
    "FillSyncService",
    "RealOrderExecutor",
    # v0.16 Phase B — KIS order client skeleton
    "FakeKisOrderTransport",
    "KisCancelResult",
    "KisFillStatusResult",
    "KisOrderClientInterface",
    "KisOrderRequest",
    "KisOrderResult",
    "mask_sensitive_order_payload",
    # v1.0 Phase B — KIS real httpx transport
    "HttpxKisOrderTransport",
    "PlaceClassification",
    "FillClassification",
    "CancelClassification",
    # v0.14 Phase B — paper trading simulator
    "ExecutePendingResult",
    "PaperTradingDisabledError",
    "SimulationBroker",
    "SimulationBrokerError",
    "SubmitResult",
]
