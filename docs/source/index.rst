dcc
===

``dcc`` is a Python-based, primarily command line driven tool for interacting with the
`LIGO DCC <https://dcc.ligo.org/>`__.

``dcc`` attempts to provide a powerful yet intuitive and user-friendly command line
interface to the DCC, allowing for quick and automated retrieval and update of records
and files.

Features
--------

- Interactive command line interface
- Retrieval and modification of DCC record metadata
- Extraction of attachment descriptions and URLs
- Local archival of downloaded content
- URL scraping and automatic, recursive archival of related documents and files

Easy to install
---------------

``dcc`` is available on `PyPI <https://pypi.org/project/dcc>`__, installable using your
favourite package manager, e.g.:

.. code-block:: text

    $ pip install dcc

See :ref:`installation`.

Easy to use
-----------

View a DCC record:

.. code-block:: text

    $ dcc view T010075
    number: T010075-v3
    url: https://dcc.ligo.org/T010075-v3
    title: Advanced LIGO Systems Design
    ...etc...

Archive a record and its files locally:

.. code-block:: text

    $ dcc archive -s /path/to/archive --files T010075
    $ tree /path/to/archive
    /path/to/archive
    └── T010075
        └── T010075-v3
            ├── Change Record for T010075-v3.docx
            ├── Change Record for T010075-v3.pdf
            ├── meta.toml
            ├── T010075-v3 aLIGO System Description.pdf
            └── T010075-v3 System Description.zip

Get help:

.. command-output:: dcc --help

See :ref:`quick_start`.

Full contents
-------------

.. toctree::
    :maxdepth: 2

    installation
    quick-start
    usage
    cli
    developers
    api

Indices and tables
==================

* :ref:`genindex`
