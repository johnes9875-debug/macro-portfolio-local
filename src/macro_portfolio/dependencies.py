from __future__ import annotations


def require_objects(namespace: dict, names, *, stage: str = "current stage") -> None:
    """Fail early with a clear dependency message instead of a downstream NameError."""
    missing = [name for name in names if name not in namespace]
    if missing:
        raise RuntimeError(
            f"{stage} is missing upstream runtime object(s): {missing}. "
            "Start a fresh run from the beginning; do not skip upstream sections."
        )
