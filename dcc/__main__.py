#!/usr/bin/env python3

import sys
import logging
from html2text import html2text
import click

from . import __version__, PROGRAM, DESCRIPTION
from .records import DCCArchive, DCCNumber, DCCAuthor
from .sessions import DCCSession
from .parsers import DCCParser
from .env import DEFAULT_HOST, DEFAULT_IDP
from .exceptions import (
    NotLoggedInError,
    UnrecognisedDCCRecordError,
    UnauthorisedError,
    FileTooLargeError,
    DryRun,
)


# Configure logging to stderr.
logging.basicConfig()


def _set_progress(ctx, _, value):
    """Set progress flag."""
    state = ctx.ensure_object(_State)
    state.show_progress = value


def _set_verbosity(ctx, param, value):
    """Set verbosity."""
    state = ctx.ensure_object(_State)

    # Quiet verbosity is negative.
    if param.name == "quiet":
        value = -value

    state.verbosity = value


def _set_dcc_host(ctx, _, value):
    """Set DCC host."""
    state = ctx.ensure_object(_State)
    state.dcc_host = value


def _set_idp_host(ctx, _, value):
    """Set identity provide host."""
    state = ctx.ensure_object(_State)
    state.idp_host = value


def _set_archive_dir(ctx, _, value):
    """Set archive directory."""
    state = ctx.ensure_object(_State)
    state.archive_dir = value


def _set_prefer_archive(ctx, _, value):
    """Set prefer archive flag."""
    state = ctx.ensure_object(_State)
    state.prefer_archive = value


def _set_overwrite(ctx, _, value):
    """Set overwrite flag."""
    state = ctx.ensure_object(_State)
    state.overwrite = value


def _set_dry_run(ctx, _, value):
    """Set dry run flag."""
    state = ctx.ensure_object(_State)
    state.dry_run = value


def _set_max_file_size(ctx, _, value):
    """Set max file size."""
    state = ctx.ensure_object(_State)
    if value is not None:
        value = value * 1024 * 1024  # Convert to bytes.
    state.max_file_size = value


download_progress_option = click.option(
    "--progress/--no-progress",
    is_flag=True,
    default=True,
    callback=_set_progress,
    expose_value=False,
    help="Show progress bar.",
)
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
archive_dir_option = click.option(
    "-s",
    "--archive-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    envvar="DCC_ARCHIVE",
    callback=_set_archive_dir,
    expose_value=False,
    help=(
        "Directory to use to archive and retrieve downloaded documents and files. "
        "If not specified, the DCC_ARCHIVE environment variable is used if set, "
        "otherwise defaults to the system's temporary directory. To persist archive "
        "data across invocations of the tool, ensure this is set to a non-temporary "
        "directory."
    ),
)
prefer_archive_option = click.option(
    "--prefer-archive",
    is_flag=True,
    default=False,
    show_default=True,
    callback=_set_prefer_archive,
    expose_value=False,
    help=(
        "When DCC_NUMBER doesn't contain a version, prefer latest archived record over "
        "the latest remote record."
    ),
)
force_option = click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    show_default=True,
    callback=_set_overwrite,
    expose_value=False,
    help="Always fetch from DCC host and overwrite existing archive data.",
)
dry_run_option = click.option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    show_default=True,
    callback=_set_dry_run,
    expose_value=False,
    help="Perform a trial run with no changes made.",
)
max_file_size_option = click.option(
    "--max-file-size",
    type=click.IntRange(min=0),
    callback=_set_max_file_size,
    expose_value=False,
    help=(
        "Maximum file size to download, in MB. If larger, the file is skipped. Note: "
        "this behaviour relies on the server providing a Content-Length header. If it "
        "does not, the file is downloaded regardless of its real size."
    ),
)
dcc_host_option = click.option(
    "--host",
    callback=_set_dcc_host,
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
    callback=_set_idp_host,
    envvar="ECP_IDP",
    default=DEFAULT_IDP,
    expose_value=False,
    help=(
        f"The identity provider host to use. If not specified, the ECP_IDP environment "
        f"variable is used if set, otherwise {repr(DEFAULT_IDP)}."
    ),
)


def echo_key(key, separator=True, nl=True):
    key = click.style(key, fg="green")
    if separator:
        key = f"{key}: "
    click.echo(key, nl=nl)


def echo_value(value):
    click.echo(value)


def echo_key_value(key, value):
    echo_key(key, separator=True, nl=False)
    echo_value(value)


def echo_record(record, session):
    echo_key_value("number", record.dcc_number)
    echo_key_value("url", session.dcc_record_url(record.dcc_number))
    echo_key_value("title", record.title)
    echo_key_value("modified", record.contents_revision_date)
    echo_key_value(
        "authors", ", ".join([author.name.strip() for author in record.authors])
    )
    echo_key("abstract")
    if record.abstract:
        echo_value(html2text(record.abstract).strip())
    echo_key("note")
    if record.note:
        echo_value(html2text(record.note).strip())
    echo_key_value("keywords", ", ".join(record.keywords))
    echo_key("files")
    for i, file_ in enumerate(record.files, start=1):
        echo_value(f"{i}. {file_}")
    echo_key_value(
        "referenced by", ", ".join([str(ref) for ref in record.referenced_by])
    )
    echo_key_value("related to", ", ".join([str(ref) for ref in record.related_to]))


def _archive_record(
    archive, dcc_number, depth, fetch_related, fetch_referencing, files, session
):
    count = 0
    # Codes already seen.
    seen = set()

    def _do_fetch(number, level=0):
        nonlocal count

        indent = "-" * (depth - level)

        cnum = click.style(str(number), fg="green")
        click.echo(f"{indent}Fetching {cnum}...")

        try:
            record = archive.fetch_record(number, session=session)
        except UnrecognisedDCCRecordError:
            click.echo(
                f"{indent}Could not find DCC document {repr(number)}; skipping.",
                err=True,
            )
            return
        except (NotLoggedInError, UnauthorisedError):
            click.echo(
                f"{indent}You are not authorised to access {number}; skipping.",
                err=True,
            )
            return

        if files:
            # Get the files.
            record.fetch_files(session=session, raise_too_large=False)

        seen.add(record.dcc_number.string_repr(version=False))

        name = click.style(str(record), fg="green")
        click.echo(f"{indent}Archived {name}")
        count += 1

        if level > 0:
            if fetch_related:
                for ref in record.related_to:
                    if ref.string_repr(version=False) in seen:
                        continue

                    _do_fetch(ref, level=level - 1)

            if fetch_referencing:
                for ref in record.referenced_by:
                    if ref.string_repr(version=False) in seen:
                        continue

                    _do_fetch(ref, level=level - 1)

    _do_fetch(dcc_number, level=depth)
    return count


class _State:
    """CLI state."""

    MIN_VERBOSITY = logging.WARNING
    MAX_VERBOSITY = logging.DEBUG

    def __init__(self):
        self.dcc_host = DEFAULT_HOST
        self.idp_host = DEFAULT_IDP
        self.archive_dir = None
        self.prefer_archive = None
        self.overwrite = None
        self.dry_run = None
        self.max_file_size = None
        self.show_progress = None
        self._verbosity = self.MIN_VERBOSITY

    def dcc_session(self):
        progress = None
        if self.show_progress:
            # Only show progress when not being quiet.
            if self.verbose:
                progress = self._download_progress_hook

        return DCCSession(
            host=self.dcc_host,
            idp=self.idp_host,
            archive_dir=self.archive_dir,
            prefer_archive=self.prefer_archive,
            overwrite=self.overwrite,
            max_file_size=self.max_file_size,
            simulate=self.dry_run,
            download_progress_hook=progress,
        )

    def _download_progress_hook(self, thing, chunks, total_length):
        # Iterate over the chunks, yielding each chunk and updating the progress bar.
        with click.progressbar(length=total_length) as progressbar:
            display_length = ""
            if total_length:
                # Convert to user friendly length.
                if total_length >= 1024 * 1024 * 1024:
                    value = total_length / (1024 * 1024 * 1024)
                    unit = "GB"
                elif total_length >= 1024 * 1024:
                    value = total_length / (1024 * 1024)
                    unit = "MB"
                elif total_length >= 1024:
                    value = total_length / 1024
                    unit = "kB"
                else:
                    value = total_length
                    unit = "B"

                display_length = f" ({value:.2f} {unit})"

            click.echo(f"Downloading {thing}{display_length}")
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
        verbosity = min(max(verbosity, self.MAX_VERBOSITY), self.MIN_VERBOSITY)
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


@click.group(name=PROGRAM, help=DESCRIPTION)
@click.version_option(version=__version__, prog_name=PROGRAM)
def dcc():
    pass


@dcc.command()
@click.argument("dcc_number", type=str)
@archive_dir_option
@prefer_archive_option
@force_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def view(ctx, dcc_number):
    """View DCC record metadata.

    DCC_NUMBER should be a DCC record designation such as 'D040105'.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    with state.dcc_session() as session:
        try:
            record = archive.fetch_record(dcc_number, session=session)
        except UnrecognisedDCCRecordError:
            click.echo(f"Could not find DCC document {repr(dcc_number)}.", err=True)
            sys.exit(1)
        except (NotLoggedInError, UnauthorisedError):
            click.echo(f"You are not authorised to access {dcc_number}.", err=True)
            sys.exit(1)

        echo_record(record, session)


@dcc.command()
@click.argument("dcc_number", type=str)
@click.option(
    "--xml",
    is_flag=True,
    default=False,
    show_default=True,
    help="Open URL for XML document.",
)
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def open(ctx, dcc_number, xml):
    """Open remote DCC record page in the default browser.

    DCC_NUMBER should be a DCC record designation such as 'D040105'.
    """
    state = ctx.ensure_object(_State)

    with state.dcc_session() as session:
        dcc_number = DCCNumber(dcc_number)
        click.echo(f"Opening {dcc_number}")
        dcc_number.open(session=session, xml=xml)


@dcc.command()
@click.argument("dcc_number", type=str)
@click.argument("file_number", type=click.IntRange(min=1))
@archive_dir_option
@prefer_archive_option
@max_file_size_option
@download_progress_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def open_file(ctx, dcc_number, file_number):
    """Open file attached to DCC record using operating system.

    DCC_NUMBER should be a DCC record designation such as D040105.

    FILE_NUMBER should be an integer starting from 1 representing the position of the
    file as listed by `dcc view DCC_NUMBER`. The file will be opened with the default
    application for its type as determined by the operating system.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    with state.dcc_session() as session:
        # Get the record.
        try:
            record = archive.fetch_record(dcc_number, session=session)
        except UnrecognisedDCCRecordError:
            click.echo(f"Could not find DCC document {repr(dcc_number)}.", err=True)
            sys.exit(1)
        except (NotLoggedInError, UnauthorisedError):
            click.echo(f"You are not authorised to access {dcc_number}.", err=True)
            sys.exit(1)

        # Get the file.
        try:
            file_ = record.fetch_file(file_number, session=session)
        except (NotLoggedInError, UnauthorisedError):
            click.echo(f"You are not authorised to access {dcc_number}.", err=True)
            sys.exit(1)
        except FileTooLargeError as err:
            click.echo(str(err), err=True)
            sys.exit(1)

        click.echo(f"Opening {file_}")
        file_.open()


@dcc.command()
@click.argument("dcc_number", type=str)
@click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Recursively fetch referencing documents up to this many levels.",
)
@click.option(
    "--fetch-related/--no-fetch-related",
    is_flag=True,
    default=True,
    show_default=True,
    help="Fetch related documents when --depth is nonzero.",
)
@click.option(
    "--fetch-referencing/--no-fetch-referencing",
    is_flag=True,
    default=False,
    show_default=True,
    help="Fetch referencing documents when --depth is nonzero.",
)
@click.option("--files", is_flag=True, default=False, help="Fetch attached files.")
@archive_dir_option
@prefer_archive_option
@max_file_size_option
@download_progress_option
@force_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def archive(ctx, dcc_number, depth, fetch_related, fetch_referencing, files):
    """Archive DCC record data.

    DCC_NUMBER should be a DCC record designation such as D040105.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    if state.archive_dir is None:
        click.echo(
            click.style(
                "Warning: -s/--archive-dir not specified. Records will be archived to "
                "a temporary directory.",
                fg="yellow",
            )
        )

    with state.dcc_session() as session:
        count = _archive_record(
            archive, dcc_number, depth, fetch_related, fetch_referencing, files, session
        )

    click.echo(f"Archived {count} record(s) at {session.archive_dir.resolve()}")


@dcc.command()
@archive_dir_option
@verbose_option
@quiet_option
@click.pass_context
def list_archive(ctx):
    """List records in the archive."""
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    if state.archive_dir is None:
        click.echo(
            click.style(
                "Warning: -s/--archive-dir not specified. Archive will be empty.",
                fg="yellow",
            )
        )

    with state.dcc_session() as session:
        for record in archive.records(session):
            echo_record(record, session)
            click.echo()


@dcc.command()
@click.argument("url", type=str)
@click.option(
    "--depth",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Recursively fetch referencing documents up to this many levels.",
)
@click.option(
    "--fetch-related/--no-fetch-related",
    is_flag=True,
    default=True,
    show_default=True,
    help="Fetch related documents when --depth is nonzero.",
)
@click.option(
    "--fetch-referencing/--no-fetch-referencing",
    is_flag=True,
    default=False,
    show_default=True,
    help="Fetch referencing documents when --depth is nonzero.",
)
@click.option("--files", is_flag=True, default=False, help="Fetch attached files.")
@archive_dir_option
@prefer_archive_option
@max_file_size_option
@download_progress_option
@force_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def scrape(ctx, url, depth, fetch_related, fetch_referencing, files):
    """Scrape URL for DCC records.

    URL should be a DCC record designation such as D040105.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    if state.archive_dir is None:
        click.echo(
            click.style(
                "Warning: -s/--archive-dir not specified. Records will be archived to "
                "a temporary directory.",
                fg="yellow",
            )
        )

    with state.dcc_session() as session:
        response = session.get(url)
        parsed = DCCParser(response.text)

        count = 0

        for dcc_number in parsed.html_dcc_numbers():
            count += _archive_record(
                archive,
                dcc_number,
                depth,
                fetch_related,
                fetch_referencing,
                files,
                session,
            )

    click.echo(f"Archived {count} record(s) at {session.archive_dir.resolve()}")


@dcc.command()
@click.argument("dcc_number", type=str)
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
@dry_run_option
@archive_dir_option
@force_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def update(ctx, dcc_number, title, abstract, keywords, note, related, authors):
    """Update DCC record metadata.

    DCC_NUMBER should be a DCC record designation such as 'D040105'.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    with state.dcc_session() as session:
        record = archive.fetch_record(dcc_number, session=session)

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

        try:
            record.update(session=session)
        except UnrecognisedDCCRecordError:
            click.echo(
                f"Could not find DCC document {repr(record.dcc_number)}.", err=True
            )
            sys.exit(1)
        except (NotLoggedInError, UnauthorisedError):
            click.echo(
                f"You are not authorised to modify {record.dcc_number}.", err=True
            )
            sys.exit(1)
        except DryRun:
            click.echo("Nothing modified.")
            sys.exit(0)

        # Save the document's changes locally. Set overwrite flag to ensure changes are
        # made.
        session.overwrite = True
        record.archive(session=session)

        click.echo(f"Successfully updated {record.dcc_number}.")


if __name__ == "__main__":
    dcc()
