import numpy as np
import pandas as pd

from macro_portfolio.numeric_safety import safe_isfinite, safe_bool_series


def test_safe_isfinite_object_series():
    s = pd.Series(["1.0", 2, None, "bad"], dtype=object)
    assert safe_isfinite(s).tolist() == [True, True, False, False]


def test_safe_isfinite_dataframe_preserves_shape():
    df = pd.DataFrame({"a": ["1", None], "b": [2.0, "bad"]})
    m = safe_isfinite(df)
    assert list(m.columns) == ["a", "b"]
    assert m.values.tolist() == [[True, True], [False, False]]


def test_safe_bool_series_strings():
    s = pd.Series([True, False, "True", "False", "1", "0", None], dtype=object)
    assert safe_bool_series(s).tolist() == [True, False, True, False, True, False, False]


def test_f5a_object_dtype_regression():
    # Reproduce the essential failure mode seen in F5A: numeric values stored in
    # an object-typed Series after optional-branch reconciliation.
    out = pd.DataFrame({
        "intrinsic_value_per_share": pd.Series(["123.4", None], dtype=object),
        "ranking_eligible_after_f5": pd.Series(["True", "False"], dtype=object),
    })
    assert safe_isfinite(out["intrinsic_value_per_share"]).tolist() == [True, False]
    assert safe_bool_series(out["ranking_eligible_after_f5"]).tolist() == [True, False]
