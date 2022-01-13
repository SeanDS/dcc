"""Environment settings."""

import os

DEFAULT_HOST = os.environ.get("DCC_HOST", "dcc.ligo.org")
DEFAULT_IDP = os.environ.get("ECP_IDP", "login.ligo.org")
