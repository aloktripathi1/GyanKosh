import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s job_id=%(job_id)s stage=%(stage)s duration_ms=%(duration_ms)s %(message)s"


class _DefaultsFilter(logging.Filter):
    """Most log records (uvicorn access logs, startup messages) don't carry
    job_id/stage/duration_ms — this fills in a placeholder so the format
    string above never KeyErrors regardless of which logger emitted it."""

    def filter(self, record: logging.LogRecord) -> bool:
        for field in ("job_id", "stage", "duration_ms"):
            if not hasattr(record, field):
                setattr(record, field, "-")
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(_DefaultsFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
