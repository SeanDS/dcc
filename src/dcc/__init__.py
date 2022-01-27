"""Tools for interactive and programmatic access to the LIGO DCC."""

PROGRAM = __name__
AUTHORS = ["Sean Leavey", "Jameson Graef Rollins", "Christopher Wipf"]
PROJECT_URL = "https://docs.ligo.org/sean-leavey/dcc/"

# Get package version.
try:
    from ._version import version as __version__
except ImportError:
    raise FileNotFoundError("Could not find version.py. Ensure you have run setup.")

# Import some modules into the package namespace.
from .records import DCCArchive, DCCNumber, DCCRecord
from .sessions import (
    default_session,
    DCCAuthenticatedSession,
    DCCUnauthenticatedSession,
)

__all__ = (
    "PROGRAM",
    "AUTHORS",
    "PROJECT_URL",
    "__version__",
    "DCCArchive",
    "DCCNumber",
    "DCCRecord",
    "default_session",
    "DCCAuthenticatedSession",
    "DCCUnauthenticatedSession",
)
