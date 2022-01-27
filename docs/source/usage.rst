.. _usage:

Usage
=====

Apart from this guide, a good place to get help is from the tool itself:

.. command-output:: dcc --help

Help for the available ``dcc`` subcommands can be shown in the same way using e.g. ``dcc
view --help``.

.. _ligo_org_authentication:

Obtaining a Kerberos ticket for accessing restricted resources
--------------------------------------------------------------

Access to most DCC records and files requires credentials such as those from `ligo.org
<https://my.ligo.org/>`__ or another provider. You typically only get these if you're a
member of a scientific collaboration.

By default, ``dcc`` assumes you can authenticate yourself and therefore builds and
requests URLs for records and files within the restricted part of the DCC, prompting for
credentials or using an existing Kerberos ticket. To avoid being prompted every time
``dcc`` is invoked, run ``kinit albert.einstein@LIGO.ORG`` (where ``albert.einstein`` is
your login and ``LIGO.ORG`` is your Kerberos realm) before first use each day (tickets
are typically granted for 24 hours). Subsequent interaction with the DCC will
transparently use a Kerberos token if one is available. The token can be verified with
``klist`` and revoked with ``kdestroy``.

You can specify the :option:`--public <dcc --public>` flag to restrict ``dcc`` to
accessing public records. With this flag, you don't need to enter your credentials or
obtain a Kerberos ticket, though you will only be able to access public resources.

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

DCC records can be archived locally using :program:`dcc archive`. This downloads
records' metadata, and optionally attached files, and stores them in the :ref:`local
archive <local_archive>` for later retrieval. The command requires one or more
:option:`NUMBER <dcc archive NUMBER>` arguments and/or a :option:`--from-file <dcc
archive --from-file>` option followed by a path to a file containing the DCC numbers
(separated by whitespace) to archive. For example:

.. code-block:: text

    # Archive the latest version of T010075:
    $ dcc archive -s /path/to/archive T010075

    # Archive a specific version of T010075:
    $ dcc archive -s /path/to/archive T010075-v1

    # Archive multiple records:
    $ dcc archive -s /path/to/archive T010075 E1300945

    # Alternatively specify the path to a file containing the records to archive:
    $ echo "T010075 E1300945" > to-archive.txt
    $ dcc archive -s /path/to/archive --from-file to-archive.txt

Similar to the behaviour of standard Unix utilities, the :option:`--from-file <dcc
archive --from-file>` option can also be set to ``stdin`` by specifying ``-``:

.. code-block:: text

    $ echo "T010075 E1300945" | dcc archive -s /path/to/archive --from-file -

Files are not automatically archived. To fetch them too, specify the :option:`--files
<dcc --files>` flag. By default, files of any size will be retrieved. To limit the
maximum size of files retrieved, specify the :option:`--max-file-size <dcc
--max-file-size>` option, specifying a maximum file size in MB.

Interactive mode
~~~~~~~~~~~~~~~~

Specifying :option:`-i <dcc archive -i>` or :option:`--interactive <dcc archive
--interactive>` will prompt you for confirmation before downloading each record's files,
giving you the opportunity to skip unnecessary files. This flag implies :option:`--files
<dcc archive --files>`.

Scraping a URL for links to DCC records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The command :program:`dcc convert` scrapes DCC numbers from a file or URL and writes
them to a file:

.. code-block:: text

    # Fetch DCC numbers in the "System Engineering" topic and write to 'out.txt'.
    $ dcc convert https://dcc.ligo.org/cgi-bin/private/DocDB/ListBy?topicid=18 out.txt

It is easy to combine :program:`dcc convert` and :program:`dcc archive` to automatically
scrape a URL for DCC numbers and archive them locally. For example:

.. code-block:: text

    # Fetch the "System Engineering" topic page, then extract and archive its DCC
    # numbers.
    $ dcc convert https://dcc.ligo.org/cgi-bin/private/DocDB/ListBy?topicid=18 - | dcc archive -s /path/to/archive --from-file -

Archival of referenced and referencing records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DCC records can contain "related to" and "referenced by" records, and :program:`dcc
archive` can archive them as well. The :option:`--depth <dcc --depth>` option controls
how far in the chain from the original documents the archival can traverse. For example,
setting :option:`--depth <dcc --depth>` to 1 will fetch the records that are listed in
the specified DCC numbers, and setting it to 2 will additionally fetch the references of
those documents. The default is 0, meaning only the records specified in the input are
fetched.

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

For example, the referenced documents of ``E1300945`` can be archived alongside
``E1300945`` itself using:

.. code-block:: text

    # Fetch "related to" documents as well as E1300945 itself:
    $ dcc archive -s /path/to/archive E1300945 --depth 1

    # Fetch "referenced by" documents as well:
    $ dcc archive -s /path/to/archive E1300945 --depth 1 --fetch-referencing

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
Einstein", and should correspond to real DCC users. For example:

.. code-block:: text

    # Update the title of T2200016.
    $ dcc update T2200016 --title "A new title"

By default, :program:`dcc update` will prompt for confirmation before sending the
updated record to the DCC. To make changes without any confirmation, specify the flag
:option:`--no-confirm <dcc update --no-confirm>`. Submitted changes are irreversible, so
be careful.

.. note::

    The DCC does not appear to perform error checking on author names. If an author is
    not given correctly, it is simply discarded.

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
