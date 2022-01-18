.. _installation:

Installation
============

``dcc`` has the following system requirements:

- Python 3.8 or later
- ``kinit`` and ``klist`` provided as part of Kerberos

Most users will find it easiest to use one of the `reference software environments
<https://computing.docs.ligo.org/guide/software/environments/>`__ provided by IGWN. The
``igwn-py38`` environment, for example, provides the required dependencies. If you
choose to manage system dependencies yourself, ensure you have the relevant Kerberos
packages above (provided on Linux by e.g. ``krb5-user`` on Debian derivatives or
``krb5-workstation`` on Red Hat derivatives).

``dcc`` can be installed using ``pip`` or your favourite Python package manager using
e.g.:

.. code-block:: text

    $ pip install dcc

To check ``dcc`` installed correctly, you can run:

.. command-output:: dcc --version

(The reported version may differ from that above.)
