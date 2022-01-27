.. _quick_start:

Quick start
===========

This section contains a quick guide to common operations in ``dcc``. For a more complete
description of features available in ``dcc``, see :ref:`usage`.

Authenticating
--------------

.. seealso:: :ref:`ligo_org_authentication`

Most DCC records and files require authentication to access, such as that provided by a
`ligo.org <https://my.ligo.org/>`__ account. By default, ``dcc`` assumes you can
authenticate yourself and therefore builds and requests URLs for records and files
within the restricted part of the DCC, prompting for credentials or using an existing
Kerberos ticket. You can specify the :option:`--public <dcc --public>` flag to restrict
``dcc`` to accessing public records.

Setting a location to store downloaded records and files
--------------------------------------------------------

.. seealso:: :ref:`local_archive`

``dcc`` works best if you give it a place to store data downloaded from the DCC, making
subsequent access to the same data faster. This can be achieved using the :option:`-s
<dcc -s>` or :option:`--archive-dir <dcc --archive-dir>` option, or by setting the
environment variable :ref:`env_dcc_archive`. The value should be a directory on your
file system. For example:

.. code-block:: text

    # Use a directory called "dcc" in your home directory.
    $ echo "T010075" | dcc archive -s ~/dcc --files -

If the archive directory is not given, ``dcc`` uses a temporary directory each time it
is invoked, and the data is lost upon program exit.

Viewing a record
----------------

Metadata for a record can be viewed on the console by specifying :program:`dcc view`
followed by the :option:`DCC number <dcc DCC_NUMBER>`, e.g.:

.. command-output:: dcc view T010075 --public

…which corresponds to what's on the `DCC page itself
<https://dcc.ligo.org/T010075/public>`__. Note that the :option:`--public <dcc
--public>` flag specifies to retrieve the record from the public DCC page.

.. note::

    Depending on the level of privilege of your credentials, you may see more or less
    information than that shown above.

Downloading and opening a file
------------------------------

The command :program:`dcc open-file` accepts a :option:`DCC number <dcc DCC_NUMBER>`
followed by a number corresponding to the file's position in the record as shown in the
file list output from :program:`dcc view`, e.g.:

.. code-block:: text

    $ dcc open-file T010075 1

``dcc`` will pass the downloaded file to the operating system to be opened using the
default application. To instead open a file browser with the downloaded file located,
pass the :option:`--locate <dcc open-file --locate>` flag.
