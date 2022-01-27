#!/usr/bin/env python3

import sys
import logging
from textwrap import dedent
from pathlib import Path
from urllib.parse import urlparse
from functools import partial
from datetime import datetime
from dataclasses import dataclass
from contextlib import contextmanager
from tempfile import TemporaryDirectory, NamedTemporaryFile
from html2text import html2text
import click

from . import __version__, PROGRAM, AUTHORS, PROJECT_URL
from .records import DCCArchive, DCCNumber, DCCAuthor
from .sessions import DCCSession, DCCAuthenticatedSession, DCCUnauthenticatedSession
from .parsers import DCCParser
from .env import DEFAULT_HOST, DEFAULT_IDP
from .util import change_exc_msg, human_file_size
from .exceptions import (
    NotLoggedInError,
    UnrecognisedDCCRecordError,
    UnauthorisedError,
    FileSkippedException,
    TooLargeFileSkippedException,
)


# Configure logging to stderr.
logging.basicConfig()


class DCCNumberType(click.ParamType):
    name = "DCC number"

    def convert(self, value, param, ctx):
        try:
            return DCCNumber(value)
        except ValueError:
            self.fail(
                f"{repr(value)}. The number should have the form 'LIGO-D040105', "
                f"'D040105', or 'D040105-v1'.",
                param,
                ctx,
            )


DCC_NUMBER_TYPE = DCCNumberType()


def _set_state_flag(ctx, _, value, *, flag):
    """Set state flag."""
    state = ctx.ensure_object(_State)
    setattr(state, flag, value)


def _set_verbosity(ctx, param, value):
    """Set state verbosity."""
    state = ctx.ensure_object(_State)

    # Quiet verbosity is negative.
    if param.name == "quiet":
        value = -value

    state.verbosity = value


def _set_max_file_size(ctx, _, value):
    """Set state max file size."""
    state = ctx.ensure_object(_State)
    if value is not None:
        value = value * 1024 * 1024  # Convert to bytes.
    state.max_file_size = value


## Arguments.
dcc_number_argument = click.argument("dcc_number", type=DCC_NUMBER_TYPE)

## Options.
# Archival.
archive_dir_option = click.option(
    "-s",
    "--archive-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    envvar="DCC_ARCHIVE",
    callback=partial(_set_state_flag, flag="archive_dir"),
    expose_value=False,
    help=(
        "Directory to use to archive and retrieve downloaded documents and files. "
        "If not specified, the DCC_ARCHIVE environment variable is used if set, "
        "otherwise defaults to the system's temporary directory. To persist archive "
        "data across invocations of the tool, ensure this is set to a non-temporary "
        "directory."
    ),
)
ignore_version_option = click.option(
    "--ignore-version",
    is_flag=True,
    default=False,
    show_default=True,
    help=(
        "Fetch the latest local version of the specified document regardless of the "
        "version given. If no local version exists, the requested (or, if no "
        "version is specified, the latest) version of the document will still be "
        "fetched from the DCC."
    ),
)
depth_option = click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Recursively fetch referencing documents up to this many levels.",
)
fetch_related_option = click.option(
    "--fetch-related/--no-fetch-related",
    is_flag=True,
    default=True,
    show_default=True,
    help="Fetch related documents when --depth is nonzero.",
)
fetch_referencing_option = click.option(
    "--fetch-referencing/--no-fetch-referencing",
    is_flag=True,
    default=False,
    show_default=True,
    help="Fetch referencing documents when --depth is nonzero.",
)
force_option = click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    show_default=True,
    help="Always fetch from DCC host and overwrite existing archive data.",
)
skip_categories_option = click.option(
    "--skip-category",
    type=click.Choice(DCCNumber.document_type_letters),
    multiple=True,
    help="Skip document type (can be specified multiple times).",
)

# Files.
files_option = click.option(
    "--files", is_flag=True, default=False, help="Fetch attached files."
)
max_file_size_option = click.option(
    "--max-file-size",
    type=click.IntRange(min=0),
    callback=_set_max_file_size,
    expose_value=False,
    help=(
        "Maximum file size to download, in MB. If larger, the file is skipped. Note: "
        "this behaviour relies on the host providing a Content-Length header. If it "
        "does not, the file is downloaded regardless of its real size."
    ),
)
download_progress_option = click.option(
    "--progress/--no-progress",
    is_flag=True,
    default=True,
    callback=partial(_set_state_flag, flag="show_progress"),
    expose_value=False,
    help="Show progress bar.",
)

# Verbosity.
verbose_option = click.option(
    "-v",
    "--verbose",
    count=True,
    callback=_set_verbosity,
    expose_value=False,
    is_eager=True,
    help="Increase verbosity (can be specified multiple times).",
)
quiet_option = click.option(
    "-q",
    "--quiet",
    count=True,
    callback=_set_verbosity,
    expose_value=False,
    help="Decrease verbosity (can be specified multiple times).",
)
debug_option = click.option(
    "--debug",
    is_flag=True,
    default=False,
    callback=partial(_set_state_flag, flag="debug"),
    expose_value=False,
    is_eager=True,
    help="Show full exceptions when errors are encountered.",
)

# Hosts.
dcc_host_option = click.option(
    "--host",
    callback=partial(_set_state_flag, flag="dcc_host"),
    envvar="DCC_HOST",
    default=DEFAULT_HOST,
    expose_value=False,
    help=(
        f"The DCC host to use. If not specified, the DCC_HOST environment variable is "
        f"used if set, otherwise {repr(DEFAULT_HOST)}."
    ),
)
idp_host_option = click.option(
    "--idp-host",
    callback=partial(_set_state_flag, flag="idp_host"),
    envvar="ECP_IDP",
    default=DEFAULT_IDP,
    expose_value=False,
    help=(
        f"The identity provider host to use. If not specified, the ECP_IDP environment "
        f"variable is used if set, otherwise {repr(DEFAULT_IDP)}."
    ),
)
public_option = click.option(
    "--public",
    is_flag=True,
    default=False,
    callback=partial(_set_state_flag, flag="public"),
    expose_value=False,
    help=(
        "Only attempt to retrieve public DCC records. This should avoid triggering an "
        "authentication check."
    ),
)


@dataclass
class ArchiveResult:
    """Results from record archival."""

    archived: int = 0
    ignored: int = 0
    unauthorised: int = 0
    unrecognised: int = 0
    other_error: int = 0
    files_archived: int = 0

    def __str__(self):
        return (
            f"Records archived: {self.archived}, ignored: {self.ignored}, "
            f"unauthorised: {self.unauthorised}, unrecognised: {self.unrecognised}, "
            f"other error: {self.other_error}.\n"
            f"Files archived: {self.files_archived}."
        )

    def __add__(self, other):
        return self.__class__(
            self.archived + other.archived,
            self.ignored + other.ignored,
            self.unauthorised + other.unauthorised,
            self.unrecognised + other.unrecognised,
            self.other_error + other.other_error,
            self.files_archived + other.files_archived,
        )


def _archive_record(
    state,
    archive,
    dcc_number,
    depth,
    fetch_related,
    fetch_referencing,
    files,
    ignore_version,
    skip_categories,
    force,
    session,
):
    result = ArchiveResult()

    # Codes already seen.
    seen = set()

    def _do_fetch(number, level=0):
        indent = "-" * (depth - level)

        number = DCCNumber(number)

        if number.category in skip_categories:
            state.echo(f"{indent}Skipping {number}.")
            result.ignored += 1
            return

        state.echo(f"{indent}Fetching {number}...")

        try:
            record = archive.fetch_record(
                number,
                ignore_version=ignore_version,
                overwrite=force,
                # Don't fetch files yet.
                fetch_files=False,
                session=session,
            )
        except UnrecognisedDCCRecordError as err:
            change_exc_msg(
                err, f"{indent}Could not find DCC document {number}; skipping"
            )
            state.echo_exception(err)
            result.unrecognised += 1
            return
        except (NotLoggedInError, UnauthorisedError) as err:
            change_exc_msg(
                err, f"{indent}You are not authorised to access {number}; skipping."
            )
            state.echo_exception(err)
            result.unauthorised += 1
            return
        except Exception as err:
            change_exc_msg(
                err, f"{indent}Error {repr(str(err))} accessing {number}; skipping."
            )
            state.echo_exception(err)
            result.other_error += 1
            return

        seen.add(record.dcc_number.format(version=False))
        result.archived += 1

        if files:
            for index in range(len(record.files)):
                try:
                    archive.fetch_record_file(
                        record,
                        index + 1,
                        ignore_too_large=True,  # Don't throw exception.
                        overwrite=force,
                        session=session,
                    )
                except FileSkippedException as err:
                    state.echo_exception(err)
                else:
                    result.files_archived += 1

        if level > 0:
            if fetch_related:
                for ref in record.related_to:
                    if ref.format(version=False) in seen:
                        continue

                    _do_fetch(ref, level=level - 1)

            if fetch_referencing:
                for ref in record.referenced_by:
                    if ref.format(version=False) in seen:
                        continue

                    _do_fetch(ref, level=level - 1)

    try:
        _do_fetch(dcc_number, level=depth)
    except click.exceptions.Abort as err:
        # Aborts during e.g. click.prompt() are not proper KeyboardInterrupts so we have
        # to make them one.
        raise KeyboardInterrupt() from err
    except Exception as err:
        change_exc_msg(err, f"Archival error: {err}")
        state.echo_exception(err)

    return result


class _State:
    """CLI state."""

    def __init__(self):
        self.dcc_host = DEFAULT_HOST
        self.idp_host = DEFAULT_IDP
        self.archive_dir = None
        self.interactive = None
        self.max_file_size = None
        self.show_progress = None
        self.public = None
        self.archive_is_temporary = None
        self.debug = None
        self._verbosity = logging.WARNING

    def dcc_session(self):
        kwargs = dict(stream_hook=self._stream_hook)

        if self.public:
            self.echo_info("Creating unauthenticated DCC session.")
            session_type = DCCUnauthenticatedSession
        else:
            self.echo_info(
                f"Creating authenticated DCC session with IDP {self.idp_host}."
            )
            session_type = DCCAuthenticatedSession
            kwargs["idp"] = self.idp_host

        return session_type(self.dcc_host, **kwargs)

    @contextmanager
    def dcc_archive(self):
        if (archive_dir := self.archive_dir) is not None:
            self.archive_is_temporary = False
            yield self._dcc_archive(archive_dir)
        else:
            # Use a temporary directory.
            self.echo_info(
                "-s/--archive-dir not specified. Downloaded records will not be "
                "persisted."
            )

            self.archive_is_temporary = True

            with TemporaryDirectory(prefix="dcc-") as archive_dir:
                self.echo_debug("Creating temporary directory for use as archive.")
                yield self._dcc_archive(archive_dir)
                self.echo_debug("Removing temporary archive.")

        # Reset.
        self.archive_is_temporary = None

    def _dcc_archive(self, archive_dir):
        archive_dir = Path(archive_dir)
        self.echo_debug(f"Using {archive_dir} as archive.")
        return DCCArchive(archive_dir)

    def _stream_hook(self, response_type, item, response):
        if response_type is not DCCSession.STREAM_FILE:
            raise RuntimeError(f"Unrecognised response type {repr(response_type)}.")

        # We're downloading a file.
        content_length = response.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            self.echo_debug(f"Content length: {content_length}")

        if self.interactive:
            if content_length:
                # Show file size.
                value, unit = human_file_size(content_length)
                item_size = f" ({value:.2f} {unit})"
            else:
                item_size = ""

            if item.exists():
                prompt = f"{repr(str(item))} already archived. Re-download{item_size}?"
            else:
                prompt = f"Download {repr(str(item))}{item_size}?"

            if not click.confirm(prompt):
                raise FileSkippedException(item)

        if content_length:
            if not self.interactive:
                if (
                    self.max_file_size is not None
                    and content_length > self.max_file_size
                ):
                    raise TooLargeFileSkippedException(
                        item, content_length, self.max_file_size
                    )

            # Only show progress when not being quiet.
            if self.show_progress and self.verbose:
                response = self._download_progress_hook(item, response, content_length)
        else:
            self.echo_debug(
                "Can't show progress or check file size: no Content-Length header."
            )

        yield from response

    def _download_progress_hook(self, item, chunks, total_length):
        # Iterate over the chunks, yielding each chunk and updating the progress bar.
        with click.progressbar(length=total_length) as progressbar:
            display_length = ""
            if total_length:
                # Convert to user friendly length.
                value, unit = human_file_size(total_length)
                display_length = f" ({value:.2f} {unit})"

            self.echo(f"Downloading {item}{display_length}")
            for chunk in chunks:
                yield chunk
                progressbar.update(len(chunk))

    @property
    def verbosity(self):
        """Verbosity on stdout."""
        return self._verbosity

    @verbosity.setter
    def verbosity(self, verbosity):
        verbosity = self._verbosity - 10 * int(verbosity)
        verbosity = min(max(verbosity, logging.DEBUG), logging.CRITICAL)
        self._verbosity = verbosity
        # Set the root logger's level.
        logging.getLogger().setLevel(self._verbosity)

    @property
    def verbose(self):
        """Verbose output enabled.

        Returns
        -------
        True if the verbosity is enough for WARNING (and lower) messages to be
        displayed; False otherwise.
        """
        return self.verbosity <= logging.WARNING

    def _echo(self, *args, err=False, exit_=False, **kwargs):
        click.echo(*args, err=err, **kwargs)

        if exit_:
            code = 1 if err else 0
            sys.exit(code)

    def echo(self, *args, **kwargs):
        if self.verbosity > logging.WARNING:
            return

        self._echo(*args, **kwargs)

    def echo_info(self, msg, *args, **kwargs):
        if self.verbosity > logging.INFO:
            return

        msg = click.style(msg, fg="blue")
        self._echo(msg, *args, **kwargs)

    def echo_error(self, msg, *args, **kwargs):
        if self.verbosity > logging.ERROR and not self.debug:
            return

        msg = click.style(msg, fg="red")
        self._echo(msg, *args, err=True, **kwargs)

    def echo_exception(self, exception, *args, **kwargs):
        if not self.debug:
            # Just echo the error string, not the traceback.
            return self.echo_error(str(exception), *args, **kwargs)

        import traceback

        should_exit = kwargs.pop("exit_", False)

        tb = "".join(traceback.format_tb(exception.__traceback__))
        self._echo(tb, *args, err=True, exit_=False, **kwargs)
        msg = click.style(str(exception), fg="red")
        self._echo(msg, *args, err=True, exit_=should_exit, **kwargs)

    def echo_warning(self, msg, *args, **kwargs):
        if self.verbosity > logging.WARNING:
            return

        msg = click.style(msg, fg="yellow")
        self._echo(msg, *args, **kwargs)

    def echo_debug(self, *args, **kwargs):
        if self.verbosity > logging.DEBUG:
            return

        self._echo(*args, **kwargs)

    def echo_key(self, key, separator=True, nl=True):
        key = click.style(key, fg="green")
        if separator:
            key = f"{key}: "
        self.echo(key, nl=nl)

    def echo_key_value(self, key, value):
        self.echo_key(key, separator=True, nl=False)
        self.echo(value)

    def echo_record(self, record, session):
        self.echo_key_value("number", record.dcc_number)
        self.echo_key_value("url", session.dcc_record_url(record.dcc_number, xml=False))
        self.echo_key_value("title", record.title)
        self.echo_key_value("modified", record.contents_revision_date)
        self.echo_key_value(
            "authors", ", ".join([author.name.strip() for author in record.authors])
        )
        self.echo_key("abstract")
        if record.abstract:
            self.echo(html2text(record.abstract).strip())
        self.echo_key("note")
        if record.note:
            self.echo(html2text(record.note).strip())
        self.echo_key_value("keywords", ", ".join(record.keywords))
        self.echo_key("files")
        for i, file_ in enumerate(record.files, start=1):
            self.echo(f"{i}. {file_}")
        self.echo_key_value(
            "referenced by", ", ".join([str(ref) for ref in record.referenced_by])
        )
        self.echo_key_value(
            "related to", ", ".join([str(ref) for ref in record.related_to])
        )


# The help text for the root command.
_DCC_HELP = f"""
    {PROGRAM} {__version__}

    Tools for viewing and updating records, metadata and files in the LIGO Document
    Control Center (DCC).

    Website: {PROJECT_URL}

    {PROGRAM} comes with ABSOLUTELY NO WARRANTY. This is free software, and you are
    welcome to redistribute it under certain conditions. See the GNU General Public
    Licence for details.

    Copyright {datetime.now().year} {", ".join(AUTHORS)}
    """
_DCC_HELP = dedent(_DCC_HELP)


@click.group(name=PROGRAM, help=_DCC_HELP)
@click.version_option(version=__version__, prog_name=PROGRAM)
def dcc():
    pass


@dcc.command()
@dcc_number_argument
@archive_dir_option
@ignore_version_option
@force_option
@dcc_host_option
@idp_host_option
@public_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def view(ctx, dcc_number, ignore_version, force):
    """View DCC record metadata.

    DCC_NUMBER should be a DCC record designation with optional version such as
    'D040105' or 'D040105-v1'.

    If DCC_NUMBER contains a version and is present in the local archive, it is used
    unless --force is specified. If DCC_NUMBER does not contain a version, a version
    exists in the local archive, and --ignore-version is specified, the latest local
    version is used. In all other cases, the latest record is fetched from the remote
    host.

    It is recommended to specify -s/--archive-dir or set the DCC_ARCHIVE environment
    variable in order to persist downloaded data across invocations of this tool.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_archive() as archive, state.dcc_session() as session:
        try:
            record = archive.fetch_record(
                dcc_number,
                ignore_version=ignore_version,
                overwrite=force,
                session=session,
            )
        except UnrecognisedDCCRecordError as err:
            change_exc_msg(err, f"Could not find DCC document {dcc_number}.")
            state.echo_exception(err, exit_=True)
        except (NotLoggedInError, UnauthorisedError) as err:
            change_exc_msg(err, f"You are not authorised to access {dcc_number}.")
            state.echo_exception(err, exit_=True)

        state.echo_record(record, session)


@dcc.command("open")
@dcc_number_argument
@click.option(
    "--xml",
    is_flag=True,
    default=False,
    show_default=True,
    help="Open URL for XML document.",
)
@dcc_host_option
@idp_host_option
@public_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def open_(ctx, dcc_number, xml):
    """Open remote DCC record page in the default browser.

    DCC_NUMBER should be a DCC record designation with optional version such as
    'D040105' or 'D040105-v1'.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_session() as session:
        state.echo_info(f"Opening {dcc_number}")
        url = session.dcc_record_url(dcc_number, xml=xml)
        click.launch(url)


@dcc.command()
@dcc_number_argument
@click.argument("file_number", type=click.IntRange(min=1))
@archive_dir_option
@ignore_version_option
@max_file_size_option
@click.option(
    "--locate",
    is_flag=True,
    default=False,
    help=(
        "Instead of opening the file, open a file browser with the downloaded file "
        "selected."
    ),
)
@download_progress_option
@force_option
@dcc_host_option
@idp_host_option
@public_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def open_file(ctx, dcc_number, file_number, ignore_version, locate, force):
    """Open file attached to DCC record using operating system.

    DCC_NUMBER should be a DCC record designation with optional version such as
    'D040105' or 'D040105-v1'.

    FILE_NUMBER should be an integer starting from 1 representing the position of the
    file as listed by 'dcc view DCC_NUMBER'. The file will be opened with the default
    application for its type as determined by the operating system. If --locate is
    specified, the file is instead selected in the default file browser.

    If DCC_NUMBER contains a version and is present in the local archive, it is used
    unless --force is specified. If DCC_NUMBER does not contain a version, a version
    exists in the local archive, and --ignore-version is specified, the latest local
    version is used. In all other cases, the latest record is fetched from the remote
    host.

    It is recommended to specify -s/--archive-dir or set the DCC_ARCHIVE environment
    variable in order to persist downloaded data across invocations of this tool.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_archive() as archive, state.dcc_session() as session:
        # Get the record.
        try:
            record = archive.fetch_record(
                dcc_number,
                ignore_version=ignore_version,
                overwrite=force,
                session=session,
            )
        except UnrecognisedDCCRecordError as err:
            change_exc_msg(err, f"Could not find DCC document {dcc_number}.")
            state.echo_exception(err, exit_=True)
        except (NotLoggedInError, UnauthorisedError) as err:
            change_exc_msg(err, f"You are not authorised to access {dcc_number}.")
            state.echo_exception(err, exit_=True)

        # Get the file.
        try:
            file_ = archive.fetch_record_file(
                record, file_number, overwrite=force, session=session
            )
        except (NotLoggedInError, UnauthorisedError) as err:
            change_exc_msg(err, f"You are not authorised to access {dcc_number}.")
            state.echo_exception(err, exit_=True)
        except FileSkippedException as err:
            state.echo_exception(err, _exit=True)

        if state.archive_is_temporary:
            # The archive is temporary, which means the file will be deleted as soon as
            # (the non-blocking, at least on Linux) :func:`click.launch` exits, which
            # prevents the application from opening it. Copy the file to a temporary
            # location that won't be # deleted when the context ends.
            temp_path = NamedTemporaryFile(
                prefix="dcc-", suffix=f"-{file_.filename}", delete=False
            )
            state.echo_debug(
                f"Copying {file_} to persistent temporary location {temp_path.name}"
            )
            file_.write(temp_path)
            path = temp_path.name
        else:
            path = file_.local_path

        state.echo_info(f"Opening {file_}")
        click.launch(str(path), locate=locate)


@dcc.command()
@click.argument("number", type=DCC_NUMBER_TYPE, nargs=-1)
@click.option(
    "--from-file", type=click.File("r"), help="Archive records specified in file."
)
@depth_option
@fetch_related_option
@fetch_referencing_option
@files_option
@click.option(
    "-i/--interactive",
    is_flag=True,
    default=False,
    callback=partial(_set_state_flag, flag="interactive"),
    expose_value=False,
    help=(
        "Enable interactive mode, which prompts for confirmation before downloading "
        "files. This flag implies --files, and --max-file-size is ignored."
    ),
)
@archive_dir_option
@ignore_version_option
@max_file_size_option
@skip_categories_option
@download_progress_option
@force_option
@dcc_host_option
@idp_host_option
@public_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def archive(
    ctx,
    number,
    from_file,
    depth,
    fetch_related,
    fetch_referencing,
    files,
    ignore_version,
    skip_category,
    force,
):
    """Archive remote DCC records locally.

    Each specified NUMBER should be a DCC record designation with optional version such
    as 'D040105' or 'D040105-v1'.

    If a DCC number contains a version and is present in the local archive, it is
    skipped unless --force is specified. If the DCC number does not contain a version, a
    version exists in the local archive, and --ignore-version is specified, its archival
    is skipped as well. In all other cases, the latest record is fetched from the remote
    host.

    It is recommended to specify -s/--archive-dir or set the DCC_ARCHIVE environment
    variable in order to persist downloaded data across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    numbers = list(number)

    with state.dcc_archive() as archive, state.dcc_session() as session:
        if from_file:
            # Extract numbers from input file.
            while file_numbers := from_file.readline():
                file_numbers = file_numbers.split()

                for number in file_numbers:
                    try:
                        number = DCCNumber(number)
                    except Exception as err:
                        state.echo_exception(f"Error parsing {repr(number)}: {err}")
                    else:
                        numbers.append(number)

        # Archive the numbers.
        result = ArchiveResult()
        try:
            for number in numbers:
                result += _archive_record(
                    state,
                    archive,
                    number,
                    depth,
                    fetch_related,
                    fetch_referencing,
                    files,
                    ignore_version,
                    skip_category,
                    force,
                    session,
                )
        finally:
            state.echo(result)


@dcc.command("list")
@archive_dir_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def list_(ctx):
    """List records in the local archive.

    It is recommended to specify -s/--archive-dir or set the DCC_ARCHIVE environment
    variable otherwise this command will list nothing.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_archive() as archive, state.dcc_session() as session:
        for record in archive.records:
            state.echo_record(record, session)
            state.echo()  # Empty line.


@dcc.command()
@click.argument("src", type=str)
@click.argument("dst", type=click.File("w"))
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def convert(ctx, src, dst):
    """Extract DCC numbers from a target file or URL.

    Any text in the document at SRC that appears to be a DCC number is written to
    DST.

    SRC can be a path to a local file or a web address.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_session() as session:
        if urlparse(src).netloc:
            # The URL is remote.
            text = session.get(src).text
        else:
            # Assume the URL is a local file.
            with click.open_file(src, "rb") as fobj:
                text = fobj.read()

        parsed = DCCParser(text)

        for dcc_number in parsed.dcc_numbers():
            dst.write(f"{dcc_number}\n")


@dcc.command()
@dcc_number_argument
@click.option("--title", type=str, help="The title.")
@click.option("--abstract", type=str, help="The abstract.")
@click.option(
    "--keyword",
    "keywords",
    type=str,
    multiple=True,
    help="A keyword (can be specified multiple times).",
)
@click.option("--note", type=str, help="The note.")
@click.option(
    "--related",
    type=str,
    multiple=True,
    help="A related document (can be specified multiple times).",
)
@click.option(
    "--author",
    "authors",
    type=str,
    multiple=True,
    help="An author (can be specified multiple times).",
)
@click.option(
    "--confirm/--no-confirm",
    is_flag=True,
    default=True,
    show_default=True,
    help="Prompt for confirmation before making changes.",
)
@archive_dir_option
@force_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@debug_option
@click.pass_context
def update(
    ctx, dcc_number, title, abstract, keywords, note, related, authors, confirm, force
):
    """Update remote DCC record metadata.

    DCC_NUMBER should be a DCC record designation with optional version such as
    'D040105' or 'D040105-v1'.

    Any metadata specified for a particular field overwrites all of the existing record
    metadata for that field.

    It is recommended to specify -s/--archive-dir or set the DCC_ARCHIVE environment
    variable in order to persist downloaded data across invocations of this tool.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_archive() as archive, state.dcc_session() as session:
        record = archive.fetch_record(dcc_number, overwrite=force, session=session)

        # Apply changes.
        if title:
            record.title = title
        if abstract:
            record.abstract = abstract
        if keywords:
            record.keywords = keywords
        if note:
            record.note = note
        if related:
            record.related_to = [DCCNumber(ref) for ref in related]
        if authors:
            record.authors = [DCCAuthor(name) for name in authors]

        state.echo_record(record, session)

        if confirm and not click.confirm("Submit changes to DCC?"):
            state.echo_error("Aborted!", exit_=True)

        try:
            record.update(session=session)
        except UnrecognisedDCCRecordError as err:
            change_exc_msg(err, f"Could not find DCC document {record.dcc_number}.")
            state.echo_exception(err, exit_=True)
        except (NotLoggedInError, UnauthorisedError) as err:
            change_exc_msg(
                err, f"You are not authorised to modify {record.dcc_number}."
            )
            state.echo_exception(err, exit_=True)

        # Save the document's changes locally. Set overwrite argument to ensure changes
        # are made.
        archive.archive_revision_metadata(record, overwrite=True)

        state.echo(f"Successfully updated {record.dcc_number}.")


if __name__ == "__main__":
    dcc()
