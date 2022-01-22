# Configuration file for the Sphinx documentation builder.

import sys
import inspect
from pathlib import Path
from datetime import datetime
import dcc
from dcc import AUTHORS, __version__

# -- Project information -----------------------------------------------------

project = "dcc"
author = ", ".join(AUTHORS)
copyright = f"{datetime.now().year}, {author}"
version = "develop" if ".dev" in __version__ else __version__
release = __version__

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.linkcode",
    "sphinxcontrib.programoutput",
    "numpydoc",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# Intersphinx.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "bs4": ("https://www.crummy.com/software/BeautifulSoup/bs4/doc/", None),
}

# -- Options for autosummary extension ---------------------------------------

# Boolean indicating whether to scan all found documents for autosummary directives, and
# to generate stub pages for each.
autosummary_generate = True

numpydoc_show_class_members = False

# -- Options for viewcode extension ------------------------------------------


def linkcode_resolve(domain, info):
    """Determine the URL corresponding to Python object.

    This code is stolen with thanks from `scipy` (view `gwpy`).
    """
    if domain != "py" or not info["module"]:
        return None

    def find_source(module, fullname):
        obj = sys.modules[module]

        for part in fullname.split("."):
            obj = getattr(obj, part)

        try:  # Unwrap a decorator.
            obj = obj.im_func.func_closure[0].cell_contents
        except (AttributeError, TypeError):
            pass

        # Get filename.
        sourcepath = Path(inspect.getsourcefile(obj))
        filename = sourcepath.relative_to(Path(dcc.__file__).parent).as_posix()
        # Get line numbers of this object.
        source, lineno = inspect.getsourcelines(obj)

        if lineno:
            return "{}#L{:d}-L{:d}".format(
                filename,
                lineno,
                lineno + len(source) - 1,
            )

        return filename

    try:
        fileref = find_source(info["module"], info["fullname"])
    except (
        AttributeError,  # Object not found.
        OSError,  # File not found.
        TypeError,  # Source for object not found.
        ValueError,  # File not from dcc.
    ):
        return None

    return f"https://git.ligo.org/sean-leavey/dcc/-/tree/{version}/dcc/{fileref}"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "insipid"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
