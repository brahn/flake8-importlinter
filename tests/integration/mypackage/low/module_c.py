# This file contains an import that violates the layers contract
# (lower layer importing from higher layer)
from mypackage.high.module_a import function_a  # This should be flagged


def function_c():
    """A function that uses an import from a higher layer."""
    return function_a()
