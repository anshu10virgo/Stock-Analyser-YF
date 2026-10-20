"""Provider-neutral errors exposed to application and presentation layers."""


class SnapshotUnavailableError(RuntimeError):
    """Raised when a configured snapshot cannot satisfy a request."""


__all__ = ["SnapshotUnavailableError"]
