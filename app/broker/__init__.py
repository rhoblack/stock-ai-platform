"""Broker boundary.

Phase B (v0.14) introduces ``SimulationBroker`` as the FIRST concrete
implementation of ``BrokerInterface``. It is an internal paper-trading
simulator -- it never imports or calls KIS / DART / RSS / any external
HTTP client. Real-broker / autotrade / KIS order placement is OUT OF
SCOPE for the entire package.
"""

from app.broker.simulation_broker import (
    ExecutePendingResult,
    PaperTradingDisabledError,
    SimulationBroker,
    SimulationBrokerError,
    SubmitResult,
)


__all__ = [
    "ExecutePendingResult",
    "PaperTradingDisabledError",
    "SimulationBroker",
    "SimulationBrokerError",
    "SubmitResult",
]
