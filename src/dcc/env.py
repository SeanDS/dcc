"""Environment settings."""

import os
from requests.utils import default_user_agent as requests_default_user_agent
from . import __version__, PROJECT_URL

DEFAULT_HOST = os.environ.get("DCC_HOST", "dcc.ligo.org")
DEFAULT_IDP = os.environ.get("ECP_IDP", "login.ligo.org")
USER_AGENT = f"{__package__}/{__version__} ({PROJECT_URL}; via {requests_default_user_agent()})"