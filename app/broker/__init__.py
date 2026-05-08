"""Broker boundary.

Phase B (v0.14) introduces ``SimulationBroker`` as the FIRST concrete
implementation of ``BrokerInterface``. It is an internal paper-trading
simulator -- it never imports or calls KIS / DART / RSS / any external
HTTP client.

Phase B (v0.16) introduces ``KisOrderClientInterface`` ABC and
``FakeKisOrderTransport`` as the skeleton for real KIS order integration.
Real HTTP transport (``KisHttpOrderTransport``) is Phase D scope.
"""

from app.broker.kis_order_client import (
    FakeKisOrderTransport,
    KisCancelResult,
    KisFillStatusResult,
    KisOrderClientInterface,
    KisOrderRequest,
    KisOrderResult,
    mask_sensitive_order_payload,
)
from app.broker.simulation_broker import (
    ExecutePendingResult,
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
    SubmitResult,
)


__all__ = [
    # v0.16 Phase B — KIS order client skeleton
    "FakeKisOrderTransport",
    "KisCancelResult",
    "KisFillStatusResult",
    "KisOrderClientInterface",
    "KisOrderRequest",
    "KisOrderResult",
    "mask_sensitive_order_payload",
    # v0.14 Phase B — paper trading simulator
    "ExecutePendingResult",
    "PaperTradingDisabledError",
    "SimulationBroker",
    "SimulationBrokerError",
    "SubmitResult",
]
