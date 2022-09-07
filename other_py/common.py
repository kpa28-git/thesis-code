# Kevin Patel
# EE 509
# 6/5/2017

import numpy as np

def _assert_all_finite(X):
    """Like assert_all_finite, but only for ndarray."""
    X = np.asanyarray(X)
    # First try an O(n) time, O(1) space solution for the common case that
    # everything is finite; fall back to O(n) space np.isfinite to prevent
    # false positives from overflow in sum method.
    if (X.dtype.char in np.typecodes['AllFloat'] and not np.isfinite(X.sum())
            and not np.isfinite(X).all()):
        raise ValueError("Input contains NaN, infinity"
                         " or a value too large for %r." % X.dtype)

def _drop_nans_idx(arr, drop_zeros=False):
    if (drop_zeros):
        return np.argwhere(np.logical_or(np.isnan(arr), arr==0))
    else:
        return np.argwhere(np.isnan(arr))
