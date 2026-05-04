import logging
from pathlib import Path


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: str = "logs",
    log_to_file: bool = False,
) -> None:
    """Configure process-wide logging with a conservative default format."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path / "app.log", encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )
