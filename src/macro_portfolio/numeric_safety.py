from __future__ import annotations

import numpy as np
import pandas as pd


def safe_isfinite(value):
    """Dtype-safe finite mask preserving pandas shape/index when practical.

    Pandas columns assembled from optional/empty model branches can carry object
    dtype even when populated values are numeric. Raw numpy.isfinite raises on
    those objects. Numeric-like values are coerced; unparseable values are False.
    """
    if isinstance(value, pd.DataFrame):
        numeric = value.apply(lambda col: pd.to_numeric(col, errors="coerce"))
        arr = np.isfinite(numeric.to_numpy(dtype=float))
        return pd.DataFrame(arr, index=value.index, columns=value.columns)
    if isinstance(value, pd.Series):
        numeric = pd.to_numeric(value, errors="coerce")
        arr = np.isfinite(numeric.to_numpy(dtype=float))
        return pd.Series(arr, index=value.index, name=value.name, dtype=bool)
    if isinstance(value, pd.Index):
        numeric = pd.to_numeric(pd.Series(value), errors="coerce")
        return np.isfinite(numeric.to_numpy(dtype=float))
    if value is None or np.isscalar(value):
        try:
            return bool(np.isfinite(float(value)))
        except (TypeError, ValueError, OverflowError):
            return False
    arr = np.asarray(value)
    if arr.dtype.kind in "biufc":
        return np.isfinite(arr)
    flat = pd.to_numeric(pd.Series(arr.reshape(-1)), errors="coerce").to_numpy(dtype=float)
    return np.isfinite(flat.reshape(arr.shape))


def safe_bool_series(value, *, default=False):
    """Normalize bool-like Series without treating string 'False' as True."""
    if not isinstance(value, pd.Series):
        value = pd.Series(value)

    def _one(x):
        if pd.isna(x):
            return bool(default)
        if isinstance(x, (bool, np.bool_)):
            return bool(x)
        if isinstance(x, (int, float, np.integer, np.floating)):
            try:
                if np.isfinite(float(x)):
                    return bool(int(x))
            except Exception:
                return bool(default)
        s = str(x).strip().lower()
        if s in {"true", "t", "yes", "y", "1"}:
            return True
        if s in {"false", "f", "no", "n", "0", "", "none", "nan"}:
            return False
        return bool(default)

    return value.map(_one).astype(bool)
