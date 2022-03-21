"""Testing utilities."""

import os
import pytest


def requires_env(*envvars):
    """Decorator to require environment variable(s) to be nonempty, otherwise skipping
    the test."""
    return pytest.mark.skipif(
        any([k is None for k in map(os.environ.get, envvars)]),
        reason=f"Required environment variable(s) {', '.join(envvars)} not defined"
    )


# Environment variables required for dcc-test.ligo.org.
requires_dcc_test_env = requires_env(
    "DCC_TEST_HOST",
    "DCC_TEST_IDP_HOST",
    "DCC_TEST_USERNAME",
    "DCC_TEST_PASSWORD"
)


# A real DCC number on the DCC test server.
# FIXME: create the document to test, when this is possible.
DCC_TEST_DCC_NUMBER = "T1600423-x0"
