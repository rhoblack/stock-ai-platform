from abc import ABC, abstractmethod
from typing import Any


class AIProviderInterface(ABC):
    """AI helper contract for explanation and report text generation."""

    @abstractmethod
    def summarize_news(self, news_items: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def judge_stock(self, stock_context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def explain_decision(self, decision_context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate_report(self, report_context: dict[str, Any]) -> str:
        raise NotImplementedError

