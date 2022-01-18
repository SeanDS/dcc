.. _usage:

Usage
=====

Apart from this guide, a good place to get help is from the tool itself:

.. command-output:: dcc --help

Help for the available ``dcc`` subcommands can be shown in the same way using e.g. ``dcc
view --help``.

.. _ligo_org_authentication:

Authenticating with the identity provider host
----------------------------------------------

Access to the DCC requires credentials such as those from `ligo.org
<https://my.ligo.org/>`__ or another provider. You typically only get these if you're a
member of a scientific collaboration.

It's easiest to authenticate once before you start using ``dcc``, by running ``kinit
albert.einstein@LIGO.ORG`` (where ``albert.einstein`` is your login). Subsequent
interaction with the DCC will transparently use this token. The token can be verified
with ``klist`` and revoked with ``kdestroy``.

If you don't first run ``kinit``, you will be asked to enter your credentials the first
time ``dcc`` interacts with the DCC, and the resulting authentication lasts only until
the program exits and you will need to enter them again the next time you run the tool.

.. _local_archive:

Configuring a local archive
---------------------------

Every ``dcc`` command that involves downloading a remote record or file can cache the
results in a local archive. This allows for quick subsequent access to the same records,
by retrieving the local copy instead of connecting to the DCC. With a configured local
archive retrieval of cached records and files is transparent, with requests being made
to the DCC only if they don't yet exist in the local archive (or if the remote version
is explicitly requested).

Downloaded data is then stored in the given directory hierarchically, e.g.:

.. code-block:: text

    $ tree /path/to/archive
    /path/to/archive
    └── T010075
        └── T010075-v3
            ├── Change Record for T010075-v3.docx
            ├── Change Record for T010075-v3.pdf
            ├── meta.toml
            ├── T010075-v3 aLIGO System Description.pdf
            └── T010075-v3 System Description.zip

The ``meta.toml`` file contains the human-readable (TOML-formatted) metadata for the
record. This can also be read by ``dcc`` using :meth:`.DCCRecord.read`.

By default, ``dcc`` uses a temporary directory for downloads that gets removed
immediately before the program exits. To persist downloaded records and files between
runs, pass the :option:`-s <dcc -s>` or :option:`--archive-dir <dcc --archive-dir>`
option to any command that supports it or set the :ref:`env_dcc_archive` environment
variable. Whichever method you use, the value should be a path (relative or absolute) to
a directory.

.. warning::

    The local archive built by ``dcc`` is not guaranteed to remain consistent with that
    of the remote DCC host. To ensure you have the latest version of a record or file,
    set the :option:`--force <dcc --force>` flag when requesting it.

Record archival
---------------

A DCC record can be archived locally using :program:`dcc archive`. This downloads a
record, and optionally its files, and stores them in the :ref:`local archive
<local_archive>` for later retrieval. For example:

.. code-block:: text

    # Archive the latest version of T010075:
    $ dcc archive T010075

    # Archive a specific version of T010075:
    $ dcc archive T010075-v1

    # Full DCC numbers are also allowed:
    $ dcc archive LIGO-T010075-v1

Files are not automatically archived. To fetch them too, specify the :option:`--files
<dcc --files>` flag. By default, files of any size will be retrieved. To limit the
maximum size of files retrieved, specify the :option:`--max-file-size <dcc
--max-file-size>` option, specifying a maximum file size in MB.

Archival of referenced and referencing records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DCC records can contain "related to" and "referenced by" records, and :program:`dcc
archive` can archive them as well. The :option:`--depth <dcc --depth>` option controls
how far from the original document the archival can take place. For example, setting
:option:`--depth <dcc --depth>` to 1 will fetch the records that are listed in the
specified DCC number, and setting it to 2 will additionally fetch the references of
those documents. The default is 0, meaning only the specified record is fetched.

When :option:`--depth <dcc --depth>` is nonzero, by default only "related to" records
are fetched. To also fetch "referenced by" records, specify the
:option:`--fetch-referencing <dcc --fetch-referencing>` flag. The fetching of "related
to" and "referenced by" records can be switched on and off using
:option:`--fetch-related <dcc --fetch-related>` / :option:`--no-fetch-related <dcc
--no-fetch-related>` and :option:`--fetch-referencing <dcc --fetch-referencing>` /
:option:`--no-fetch-referencing <dcc --no-fetch-referencing>`, respectively.

.. warning::

    The DCC is a highly connected graph and as such setting a high :option:`--depth <dcc
    --depth>` is likely to lead to thousands of records being downloaded. Typically only
    a value of 1 or 2 is sufficient to archive almost every relevant related record.

For example, the referenced documents of ``T010075`` can be archived alongside
``T010075`` itself using:

.. code-block:: text

    # Fetch "related to" documents as well as T010075 itself:
    $ dcc archive T010075 --depth 1

    # Fetch "referenced by" documents as well:
    $ dcc archive T010075 --depth 1 --fetch-referencing

Scraping a URL for links to DCC records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The command :program:`dcc scrape` is similar to :program:`dcc archive`, but it scrapes
DCC numbers from a URL instead of a record. It shares the same parameters and options as
:program:`dcc archive` but instead parses the specified URL, looks for DCC numbers, and
archives each of them in turn. This can be used for example to fetch records in a
particular DCC category:

.. code-block:: text

    # Fetch records in the "System Engineering" topic:
    $ dcc scrape https://dcc.ligo.org/cgi-bin/private/DocDB/ListBy?topicid=18

.. _updating_record_metadata:

Updating record metadata
------------------------

Record metadata can be updated via ``dcc`` using :program:`dcc update`. This accepts a
:option:`DCC number <dcc DCC_NUMBER>` and one or more of the following options:
:option:`--title <dcc update --title>`, :option:`--abstract <dcc update --abstract>`,
:option:`--keyword <dcc update --keyword>`, :option:`--note <dcc update --note>`,
:option:`--related <dcc update --related>`, and :option:`--author <dcc update
--author>`.

The :option:`--keyword <dcc update --keyword>`, :option:`--related <dcc update
--related>`, and :option:`--author <dcc update --author>` options can be specified
multiple times to set multiple values. Author names should be as written, e.g. "Albert
Einstein", and should correspond to real DCC users.

.. note::

    The DCC does not appear to perform error checking on author names. If an author is
    not given correctly, it is simply discarded.

A dry run can be performed, meaning nothing actually gets updated on the remote DCC
host, by specifying the :option:`-n <dcc -n>` or :option:`--dry-run <dcc --dry-run>`
flag. Used in combination with :option:`-v <dcc -v>`, this can give you an idea of the
changes that will be made to the record without actually making them.

.. _changing_host:

Changing the DCC or login host
------------------------------

By default, ``dcc`` interacts with the DCC host at https://dcc.ligo.org/, or that of the
environment variable ``DCC_HOST`` if set. Some users may wish to change this to
something different, such as one of the backup servers (https://dcc-backup.ligo.org/,
https://dcc-lho.ligo.org/, https://dcc-llo.ligo.org/) or a DCC server for a different
project (e.g. https://dcc.cosmicexplorer.org/). This can be done by specifying a
different host using the :option:`--host <dcc --host>` flag on commands that support it.

.. warning::

    ``dcc`` does not distinguish between DCC hosts when archiving records and files
    locally. To prevent mixing records from separate projects within the same hierarchy,
    specify a different :ref:`local archive <local_archive>` setting for each project.

It is also possible to change the identity provider (IDP) host, used to authenticate
your login credentials. By default it is set to https://login.ligo.org/, or that of the
environment variable ``ECP_IDP``, but can be changed to the backup
(https://login2.ligo.org/) or that of another project (see `cilogon.org
<https://cilogon.org/include/ecpidps.txt>`__ for a list of available IDP hosts) using
the :option:`--idp-host <dcc --idp-host>` flag on commands that support it.
