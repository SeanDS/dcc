"""Tools for interactive and programmatic access to the LIGO DCC."""

import locale

PROGRAM = __name__
AUTHORS = ["Sean Leavey", "Jameson Graef Rollins"]
PROJECT_URL = "https://git.ligo.org/sean-leavey/dcc/"

# Set the locale to the user's default (required for e.g. number formatting in log
# warnings).
locale.setlocale(locale.LC_ALL, "")

# Get package version.
try:
    from ._version import version as __version__
except ImportError:
    raise Exception("Could not find version.py. Ensure you have run setup.")

__all__ = ("PROGRAM", "AUTHORS", "PROJECT_URL", "__version__")
