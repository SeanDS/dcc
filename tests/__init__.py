import pytest

# Register testing module assertion error rewriting.
# NOTE: this needs to happen before the testing module is actually imported by any other
# test code.
pytest.register_assert_rewrite("dcc.testing")
