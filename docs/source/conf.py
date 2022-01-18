# Configuration file for the Sphinx documentation builder.

from datetime import datetime
from dcc import AUTHORS

# -- Project information -----------------------------------------------------

project = "dcc"
author = ", ".join(AUTHORS)
copyright = f"{datetime.now().year}, {author}"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
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

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "insipid"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]
