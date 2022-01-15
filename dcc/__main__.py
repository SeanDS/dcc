#!/usr/bin/env python3

import sys
import logging
from html2text import html2text
import click

from . import __version__, PROGRAM, DESCRIPTION
from .records import DCCArchive, DCCNumber, DCCAuthor
from .sessions import DCCSession
from .env import DEFAULT_HOST, DEFAULT_IDP
from .exceptions import (
    NotLoggedInError,
    UnrecognisedDCCRecordError,
    UnauthorisedError,
    DryRun,
)


# Configure logging to stderr.
logging.basicConfig()


def _set_verbosity(ctx, _, value):
    """Set verbosity."""
    state = ctx.ensure_object(_State)
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
            record = archive.fetch_record(number, fetch_files=files, session=session)
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
        self.dcc_host = None
        self.idp_host = None
        self.archive_dir = None
        self.prefer_archive = None
        self.overwrite = None
        self.dry_run = None
        self._verbosity = self.MIN_VERBOSITY

    def dcc_session(self):
        return DCCSession(
            host=self.dcc_host,
            idp=self.idp_host,
            archive_dir=self.archive_dir,
            prefer_archive=self.prefer_archive,
            overwrite=self.overwrite,
            simulate=self.dry_run,
        )

    @property
    def verbosity(self):
        """Verbosity on stdout."""
        return self._verbosity

    @verbosity.setter
    def verbosity(self, verbosity):
        verbosity = self._verbosity - 10 * int(verbosity)
        self._verbosity = min(max(verbosity, self.MAX_VERBOSITY), self.MIN_VERBOSITY)
        # Set the root logger's level.
        logging.getLogger().setLevel(self._verbosity)

    @property
    def verbose(self):
        """Verbose output enabled.

        Returns
        -------
        True if the verbosity is enough for INFO/DEBUG messages to be displayed; False
        otherwise.
        """
        return self.verbosity <= logging.INFO


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
        click.echo()


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
@click.argument("file_number", type=click.IntRange(min=1), nargs=-1)
@archive_dir_option
@prefer_archive_option
@dcc_host_option
@idp_host_option
@verbose_option
@quiet_option
@click.pass_context
def open_file(ctx, dcc_number, file_number):
    """Open file(s) attached to DCC record using operating system.

    DCC_NUMBER should be a DCC record designation such as D040105.

    FILE_NUMBER should be an integer starting from 1 representing the position of the
    file as listed by `dcc view DCC_NUMBER`. Zero or more numbers can be specified, and
    all will be opened with the default application for the file type as determined by
    the operating system.

    It is recommended to specify -s/--archive-dir in order to persist downloaded data
    across invocations of this tool.
    """
    state = ctx.ensure_object(_State)
    archive = DCCArchive()

    with state.dcc_session() as session:
        try:
            record = archive.fetch_record(dcc_number, session=session)
            record.fetch_files(session=session)
        except UnrecognisedDCCRecordError:
            click.echo(f"Could not find DCC document {repr(dcc_number)}.", err=True)
            sys.exit(1)
        except (NotLoggedInError, UnauthorisedError):
            click.echo(f"You are not authorised to access {dcc_number}.", err=True)
            sys.exit(1)

        for n in file_number:
            file_ = record.files[n - 1]
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
