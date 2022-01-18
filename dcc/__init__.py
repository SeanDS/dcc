"""Tools for interactive and programmatic access to the LIGO DCC."""

PROGRAM = __name__
AUTHORS = ["Sean Leavey", "Jameson Graef Rollins", "Christopher Wipf"]
PROJECT_URL = "https://docs.ligo.org/sean-leavey/dcc/"

# Get package version.
try:
    from ._version import version as __version__
except ImportError:
    raise Exception("Could not find version.py. Ensure you have run setup.")

__all__ = ("PROGRAM", "AUTHORS", "PROJECT_URL", "__version__")
