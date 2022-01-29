.. _installation:

Installation
============

``dcc`` has the following system requirements:

- Python 3.8 or later
- ``kinit`` and ``klist`` provided as part of Kerberos

Most users will find it easiest to use one of the `reference software environments
<https://computing.docs.ligo.org/guide/software/environments/>`__ provided by IGWN. If
you choose to manage system dependencies yourself, ensure you have the relevant Kerberos
packages above (provided on Linux by e.g. ``krb5-user`` on Debian derivatives or
``krb5-workstation`` on Red Hat derivatives).

Within a IGWN reference software environment
--------------------------------------------

The IGWN `reference software environments
<https://computing.docs.ligo.org/guide/software/environments/>`__ provide the required
system dependencies in a way that should "just work" on most platforms. See the `IGWN
Conda usage guide <https://computing.docs.ligo.org/conda/usage/>`__ for more
information. To install ``dcc`` from within such an environment (e.g. ``igwn-py38``),
just run:

.. code-block:: text

    (igwn-py38) $ conda install dcc

The ``dcc`` package is available on `conda-forge
<https://anaconda.org/conda-forge/dcc>`__, which is the default channel in the IGWN
conda environments. If you encounter a "package not found" error then add the ``-c
conda-forge`` option to the above command.

From PyPI
---------

``dcc`` can be installed from `PyPI <https://pypi.org/project/dcc/>`__ using ``pip`` or
your favourite Python package manager using e.g.:

.. code-block:: text

    $ pip install dcc

To check ``dcc`` installed correctly, you can run:

.. command-output:: dcc --version

(The reported version may differ from that above.)

.. warning::

    Some packages that ``dcc`` depends on may require extra system dependencies. One
    example is `M2Crypto <https://pypi.org/project/M2Crypto/>`__ which is not (as of
    writing) provided as a binary wheel on PyPI for any platform, so requires system
    dependencies to be available already. See `this
    <https://gitlab.com/m2crypto/m2crypto/-/blob/master/INSTALL.rst>`__ for a list of
    required packages. If you encounter "no such file or directory" type errors during
    ``pip install dcc`` then ensure you have the packages listed in the dependencies.
    Feel free to open an `issue <https://git.ligo.org/sean-leavey/dcc/-/issues>`__ if
    you continue to have trouble.
