# This file contains a forbidden import
from mypackage.low.module_b import function_b  # This should be flagged


def function_a():
    """A function that uses a forbidden import."""
    return function_b()
