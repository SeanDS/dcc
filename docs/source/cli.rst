Command reference
=================

Common parameters and options
-----------------------------

Some parameters and options are shared by multiple ``dcc`` subcommands.

Arguments
~~~~~~~~~

Arguments are positional, and are usually required by commands that support them.

.. program:: dcc

.. option:: DCC_NUMBER

    A DCC number.

Options and flags
~~~~~~~~~~~~~~~~~

Options and flags are optional parameters that change the behaviour of a command.
Options require a value of some sort, whereas flags don't.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: --ignore-version

    Attempt to fetch the latest version of the document specified in :option:`DCC_NUMBER
    <dcc DCC_NUMBER>` from the local archive regardless of the version specified. If no
    local version exists, the version of the document given in :option:`DCC_NUMBER <dcc
    DCC_NUMBER>` (or, if no version is specified, the latest version) will still be
    fetched from the DCC.

.. option:: --depth

    Recursively fetch referencing documents up to this many levels.

.. option:: --fetch-related, --no-fetch-related

    Fetch related documents when :option:`--depth <dcc --depth>` is nonzero.

.. option:: --fetch-referencing, --no-fetch-referencing

    Fetch referencing documents when :option:`--depth <dcc --depth>` is nonzero.

.. option:: -f, --force

    Force retrieval of a record or file from the remote DCC host even if it exists in
    the local archive. The locally archived record or file is overwritten with the
    retrieved version.

.. option:: --skip-category

    Skip retrieval of a particular document type, such as ``M`` ("Management or
    Policy"). This can be specified multiple times, for different document types.

.. option:: --files

    In addition to fetching the record, fetch its attached files too.

.. option:: --max-file-size

    Maximum file size to download, in MB. If larger, the file is skipped. Note: this
    behaviour relies on the DCC host providing a ``Content-Length`` header. If it does
    not, the file is downloaded regardless of its real size.

.. option:: --progress, --no-progress

    Show or hide a download progress bar. For small files the progress bar may not be
    shown. By default this is enabled.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: --public

    Only attempt to retrieve public DCC records. This should avoid triggering an
    authentication check.

``dcc archive``
---------------

.. program:: dcc archive

Archive remote DCC records locally.

Each specified :option:`NUMBER <dcc archive NUMBER>` should be a DCC record designation
with optional version such as 'D040105' or 'D040105-v1'.

If a DCC number contains a version and is present in the local archive, it is skipped
unless :option:`--force <dcc archive --force>` is specified. If the DCC number does not
contain a version, a version exists in the local archive, and :option:`--ignore-version
<dcc archive --ignore-version>` is specified, its archival is skipped as well. In all
other cases, the latest record is fetched from the remote host.

.. option:: NUMBER

    A DCC number to archive (can be specified multiple times).

.. option:: --from-file

    Archive records specified in file.

.. option:: --depth

    Recursively fetch referencing documents up to this many levels.

.. option:: --fetch-related, --no-fetch-related

    Fetch related documents when :option:`--depth <dcc --depth>` is nonzero.

.. option:: --fetch-referencing, --no-fetch-referencing

    Fetch referencing documents when :option:`--depth <dcc --depth>` is nonzero.

.. option:: --files

    In addition to fetching the record, fetch its attached files too.

.. option:: -i, --interactive

    Enable interactive mode, which prompts for confirmation before downloading files.
    This flag implies :option:`--files <dcc archive --files>`, and
    :option:`--max-file-size <dcc archive --max-file-size>` is ignored.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: --ignore-version

    Attempt to fetch the latest version of each DCC number from the local archive
    regardless of the version specified. If no local version exists, the version of the
    document given in the DCC number (or, if no version is specified, the latest
    version) will still be fetched from the DCC.

.. option:: --max-file-size

    Maximum file size to download, in MB. If larger, the file is skipped. Note: this
    behaviour relies on the DCC host providing a ``Content-Length`` header. If it does
    not, the file is downloaded regardless of its real size.

.. option:: --skip-category

    Skip retrieval of a particular document type, such as ``M`` ("Management or
    Policy"). This can be specified multiple times, for different document types.

.. option:: --progress, --no-progress

    Show or hide a download progress bar. For small files the progress bar may not be
    shown. By default this is enabled.

.. option:: -f, --force

    Force retrieval of a record or file from the remote DCC host even if it exists in
    the local archive. The locally archived record or file is overwritten with the
    retrieved version.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: --public

    Only attempt to retrieve public DCC records. This should avoid triggering an
    authentication check.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc convert``
---------------

.. program:: dcc convert

Extract DCC numbers from a target file or URL and write to DST.

Any text in the document at :option:`SRC <dcc convert SRC>` that appears to be a DCC
number is written to :option:`DST <dcc convert DST>`.

:option:`SRC <dcc convert SRC>` can be a path to a local file (or stdin) or a web
address.

.. option:: SRC

    The file or URL to scrape for DCC numbers. Can be a path to a local file or a web
    address.

.. option:: DST

    The file to write extracted DCC numbers to.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc list``
------------

.. program:: dcc list

List records in the local archive.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc open``
------------

.. program:: dcc open

Open remote DCC record page in the default browser.

:option:`DCC_NUMBER <dcc open DCC_NUMBER>` should be a DCC record designation with
optional version such as ``D040105`` or ``D040105-v1``.

.. option:: DCC_NUMBER

    The number for the DCC record to archive.

.. option:: --xml

    Open URL for XML document.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: --public

    Only attempt to retrieve public DCC records. This should avoid triggering an
    authentication check.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc open-file``
-----------------

.. program:: dcc open-file

Open file attached to DCC record using operating system.

:option:`DCC_NUMBER <dcc open-file DCC_NUMBER>` should be a DCC record designation with
optional version such as ``D040105`` or ``D040105-v1``.

:option:`FILE_NUMBER <dcc open-file FILE_NUMBER>` should be an integer starting from 1
representing the position of the file as listed by ``dcc view DCC_NUMBER``. The file
will be opened with the default application for its type as determined by the operating
system. If :option:`--locate <dcc open-file --locate>` is specified, the file is instead
selected in the default file browser.

If :option:`DCC_NUMBER <dcc open-file DCC_NUMBER>` contains a version and is present in
the local archive, it is used unless :option:`--force <dcc open-file --force>` is
specified. If :option:`DCC_NUMBER <dcc open-file DCC_NUMBER>` does not contain a
version, a version exists in the local archive, and :option:`--ignore-version <dcc
open-file --ignore-version>` is specified, the latest local version is used. In all
other cases, the latest record is fetched from the remote host.

.. option:: DCC_NUMBER

    The number for the DCC record to archive.

.. option:: FILE_NUMBER

    The file number to open.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: --ignore-version

    Attempt to fetch the latest version of the document specified in :option:`DCC_NUMBER
    <dcc open-file DCC_NUMBER>` from the local archive regardless of the version
    specified. If no local version exists, the version of the document given in
    :option:`DCC_NUMBER <dcc open-file DCC_NUMBER>` (or, if no version is specified, the
    latest version) will still be fetched from the DCC.

.. option:: --max-file-size

    Maximum file size to download, in MB. If larger, the file is skipped. Note: this
    behaviour relies on the DCC host providing a ``Content-Length`` header. If it does
    not, the file is downloaded regardless of its real size.

.. option:: --locate

    Instead of opening the file, open a file browser with the downloaded file selected.

.. option:: --progress, --no-progress

    Show or hide a download progress bar. For small files the progress bar may not be
    shown. By default this is enabled.

.. option:: -f, --force

    Force retrieval of a record or file from the remote DCC host even if it exists in
    the local archive. The locally archived record or file is overwritten with the
    retrieved version.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: --public

    Only attempt to retrieve public DCC records. This should avoid triggering an
    authentication check.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc update``
--------------

.. program:: dcc update

Update remote DCC record metadata.

:option:`DCC_NUMBER <dcc update DCC_NUMBER>` should be a DCC record designation with
optional version such as ``D040105`` or ``D040105-v1``.

Any metadata specified for a particular field overwrites all of the existing record
metadata for that field.

.. option:: DCC_NUMBER

    The number for the DCC record to update.

.. option:: --title

    The new title.

.. option:: --abstract

    The new abstract.

.. option:: --keyword

    A keyword (can be specified multiple times).

.. option:: --note

    The new note.

.. option:: --related

    A new related document number (can be specified multiple times).

.. option:: --author

    An author in the form "Albert Einstein" (can be specified multiple times).

.. option:: --confirm, --no-confirm

    Prompt (``--confirm``) or don't prompt (``--no-confirm``) for confirmation before
    actually submitting the update to the remote DCC host.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: -f, --force

    Force retrieval of a record or file from the remote DCC host even if it exists in
    the local archive. The locally archived record or file is overwritten with the
    retrieved version.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

``dcc view``
------------

.. program:: dcc view

View DCC record metadata.

:option:`DCC_NUMBER <dcc view DCC_NUMBER>` should be a DCC record designation with
optional version such as ``D040105`` or ``D040105-v1``.

If :option:`DCC_NUMBER <dcc view DCC_NUMBER>` contains a version and is present in the
local archive, it is used unless :option:`--force <dcc view --force>` is specified. If
:option:`DCC_NUMBER <dcc view DCC_NUMBER>` does not contain a version, a version exists
in the local archive, and :option:`--ignore-version <dcc view --ignore-version>` is
specified, the latest local version is used. In all other cases, the latest record is
fetched from the remote host.

.. option:: DCC_NUMBER

    The number for the DCC record to view.

.. option:: -s, --archive-dir

    Directory to use to archive and retrieve downloaded documents and files. If not
    specified, the :ref:`DCC_ARCHIVE <env_dcc_archive>` environment variable is used if
    set, otherwise defaults to the system's temporary directory (e.g. ``/tmp`` on
    Linux). To persist archive data across invocations of the tool, ensure this option
    is set.

.. option:: --ignore-version

    Attempt to fetch the latest version of the document specified in :option:`DCC_NUMBER
    <dcc view DCC_NUMBER>` from the local archive regardless of the version specified.
    If no local version exists, the version of the document given in :option:`DCC_NUMBER
    <dcc view DCC_NUMBER>` (or, if no version is specified, the latest version) will
    still be fetched from the DCC.

.. option:: -f, --force

    Force retrieval of a record or file from the remote DCC host even if it exists in
    the local archive. The locally archived record or file is overwritten with the
    retrieved version.

.. option:: --host

    The DCC host to use. If not specified, the :ref:`DCC_HOST <env_dcc_host>`
    environment variable is used if set, otherwise https://dcc.ligo.org/.

.. option:: --idp-host

    The identity provider host to use. If not specified, the :ref:`ECP_IDP
    <env_idp_host>` environment variable is used if set, otherwise
    https://login.ligo.org/.

.. option:: --public

    Only attempt to retrieve public DCC records. This should avoid triggering an
    authentication check.

.. option:: -v, --verbose

    Increase the program's verbosity. This can be specified multiple times to further
    increase verbosity.

.. option:: -q, --quiet

    Decrease the program's verbosity. This can be specified multiple times to further
    decrease verbosity.

.. option:: --debug

    Show full exceptions when errors are encountered.

Environment variables
---------------------

.. _env_dcc_archive:

``DCC_ARCHIVE``
~~~~~~~~~~~~~~~

.. seealso:: :ref:`local_archive`

The path to a local directory to use to archive downloaded records and files.

.. _env_dcc_host:

``DCC_HOST``
~~~~~~~~~~~~

.. seealso:: :ref:`changing_host`

The DCC host to use.

.. _env_idp_host:

``ECP_IDP``
~~~~~~~~~~~

.. seealso:: :ref:`changing_host`

The identity provider host to use.
