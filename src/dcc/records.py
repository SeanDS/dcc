"""Record objects."""

import logging
from typing import List
from pathlib import Path
import shutil
from dataclasses import dataclass, field, asdict
from itertools import takewhile
from functools import total_ordering, wraps
import datetime
import tomli
import tomli_w
from .sessions import default_session
from .parsers import DCCXMLRecordParser, DCCXMLUpdateParser
from .util import opened_file, remove_none
from .exceptions import NoVersionError, TooLargeFileSkippedException

LOGGER = logging.getLogger(__name__)


def ensure_session(func):
    """Ensure the `session` argument passed to the wrapped function is real, creating a
    temporary session if required."""

    @wraps(func)
    def wrapped(*args, session=None, **kwargs):
        if session is None:
            LOGGER.debug(f"Using default session for called {func}.")
            with default_session() as session:
                return func(*args, session=session, **kwargs)

        return func(*args, session=session, **kwargs)

    return wrapped


class DCCArchive:
    """A local collection of DCC documents.

    This acts as an offline store of previously downloaded DCC documents.

    Parameters
    ----------
    archive_dir : str or :class:`pathlib.Path`
        The archive directory on the local file system to store retrieved records and
        files in.
    """

    def __init__(self, archive_dir):
        self.archive_dir = Path(archive_dir)

    @property
    def documents(self):
        """The documents in the local archive.

        These are DCC numbers corresponding to the documents in the local archive,
        without version suffices.

        Yields
        ------
        :class:`.DCCNumber`
            A DCC number in the local archive.
        """
        for path in self.archive_dir.iterdir():
            if not path.is_dir():
                continue

            try:
                yield DCCNumber(path.name)
            except Exception:
                # Not a valid DCC number.
                pass

    @property
    def records(self):
        """Records in the local archive, including revisions.

        Yields
        ------
        :class:`.DCCRecord`
            A record in the archive.
        """
        for document in self.documents:
            path = self.document_dir(document)
            yield from self.revisions(path.name)

    @property
    def latest_revisions(self):
        """Latest revisions of the documents in the local archive.

        Yields
        ------
        :class:`.DCCRecord`
            The latest revision of a document in the archive.
        """
        for document in self.documents:
            path = self.document_dir(document)

            try:
                yield self.latest_revision(path.name)
            except Exception:
                # Not a valid DCC record.
                pass

    @ensure_session
    def fetch_record(
        self,
        dcc_number,
        *,
        ignore_version=False,
        overwrite=False,
        fetch_files=False,
        ignore_too_large=False,
        session,
    ):
        """Fetch a DCC record, either from the local archive or from the remote DCC
        host, adding it to the local archive if necessary.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC record to fetch.

        ignore_version : bool, optional
            Whether to ignore the version in `dcc_number` when deterimining if the
            document exists in the archive already. Defaults to False.

        overwrite : bool, optional
            Whether to overwrite existing records and files in the archive with those
            fetched remotely. Defaults to False.

        fetch_files : bool, optional
            Whether to also fetch the files attached to the record. Defaults to False.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a
            :class:`.TooLargeFileSkippedException`. If True, the file is simply ignored.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        dcc_number = DCCNumber(dcc_number)

        record = None

        if dcc_number.version is None:
            LOGGER.info(
                f"No version specified in requested record {repr(str(dcc_number))}."
            )

            if ignore_version:
                # Use the latest archived record, if found.
                LOGGER.info(
                    "Searching for latest record in the local archive (disable by "
                    "setting ignore_version to False)."
                )
                try:
                    record = self.latest_revision(dcc_number)
                except FileNotFoundError:
                    LOGGER.info("No locally archived record of any version exists.")
                else:
                    LOGGER.info("Found record in local archive.")
            else:
                # We can't know for sure that the local archive contains the latest
                # version, so we have to fetch the remote.
                LOGGER.info(
                    "No version specified; fetching latest record from DCC regardless "
                    "of local archive (disable by setting ignore_version to True)."
                )
        else:
            if not overwrite:
                meta_file = self.revision_meta_path(dcc_number)

                if meta_file.exists():
                    # Retrieve the cached record.
                    LOGGER.info(f"Fetching {dcc_number} from the local archive")

                    try:
                        record = DCCRecord.read(meta_file)
                    except FileNotFoundError as err:
                        raise Exception(f"{err} (document in local archive corrupt?)")
            else:
                LOGGER.info(
                    f"Overwriting locally archived copy of {dcc_number} if present"
                )

        if record is None:
            # Fetch the remote record.
            LOGGER.info(f"Fetching {dcc_number} from DCC")
            record = DCCRecord.fetch(dcc_number, session=session)

        record.discover_files(self.revision_dir(record.dcc_number))

        # Store/update record in the local archive.
        self.archive_revision_metadata(record, overwrite=overwrite)

        if fetch_files:
            self.fetch_record_files(
                record,
                ignore_too_large=ignore_too_large,
                overwrite=overwrite,
                session=session,
            )

        return record

    @ensure_session
    def fetch_record_files(
        self, record, *, ignore_too_large=False, overwrite=False, session
    ):
        """Fetch the files in the specified DCC record. If any file does not exist in
        the local archive, it is fetched and archived from the DCC.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to fetch files for.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a
            :class:`.TooLargeFileSkippedException`. If True, the file is simply ignored.

        overwrite : bool, optional
            Whether to overwrite existing local files with those fetched remotely.
            Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Returns
        -------
        list
            The fetched :class:`files <.DCCFile>`.
        """
        return record.fetch_files(
            self.revision_dir(record.dcc_number),
            ignore_too_large=ignore_too_large,
            overwrite=overwrite,
            session=session,
        )

    @ensure_session
    def fetch_record_file(
        self, record, number, *, ignore_too_large=False, overwrite=False, session
    ):
        """Fetch the file at position `number` in the specified DCC record. If the file
        does not exist in the local archive, it is fetched and archived from the DCC.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to fetch files for.

        number : int
            The file number to fetch, as listed in the record metadata, starting from
            position 1.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a
            :class:`.TooLargeFileSkippedException`. If True, the file is simply ignored.

        overwrite : bool, optional
            Whether to overwrite existing local files with those fetched remotely.
            Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Returns
        -------
        :class:`.DCCFile`
            The fetched file.
        """
        return record.fetch_file(
            number,
            self.revision_dir(record.dcc_number),
            ignore_too_large=ignore_too_large,
            overwrite=overwrite,
            session=session,
        )

    def archive_revision_metadata(self, record, *, overwrite=False):
        """Serialise revision metadata in the local archive.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to archive.

        overwrite : bool, optional
            If True, overwrite any existing revision in the local archive; otherwise
            do nothing. Defaults to False.
        """
        meta_path = self.revision_meta_path(record.dcc_number)

        if meta_path.is_file():
            if not overwrite:
                LOGGER.info(
                    f"Refusing to overwrite existing meta file at {meta_path}; set "
                    f"overwrite to force."
                )
                return

            LOGGER.info(f"Overwriting {meta_path}")

        LOGGER.info(f"Archiving {record} metadata to {meta_path}.")
        meta_path.parent.mkdir(parents=True, exist_ok=True)

        # First write the metadata to a temporary file in the same directory, then move
        # it to the final location, to ensure atomicity.
        # Just create a new file directly (don't use `tempfile`) so that the new
        # temporary file has the target directory's intended mode.
        meta_path_tmp = meta_path.parent / f".{meta_path.name}-tmp"
        record.write(meta_path_tmp)
        # NOTE: remove str() for Python >= 3.9.
        shutil.move(str(meta_path_tmp), str(meta_path))  # Atomic when dirs match.

    def revisions(self, dcc_number):
        """All revisions in the local archive corresponding to the specified DCC number.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC number. If a version is specified, it is ignored.

        Returns
        -------
        :class:`list`
            The :class:`records <.DCCRecord>` in the local archive corresponding to the
            revisions of `dcc_number`.
        """
        dcc_number = DCCNumber(dcc_number)
        document_dir = self.document_dir(dcc_number)

        revisions = []

        if document_dir.exists():
            for revision_path in document_dir.iterdir():
                if not revision_path.is_dir():
                    continue

                # Parse the revision if exists.
                revisions.append(DCCRecord.read(self._meta_path(revision_path)))

        return revisions

    def latest_revision(self, dcc_number):
        """The latest revision in the local archive of the document corresponding to the
        specified DCC number.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC number. If a version is specified, it is ignored.

        Returns
        -------
        :class:`.DCCRecord`
            The latest revision in the local archive of `dcc_number`.

        Raises
        ------
        :class:`FileNotFoundError`
            If no revisions of `dcc_number` exist in the local archive.
        """
        records = self.revisions(dcc_number)
        try:
            # Return the record with the latest version.
            return max(records, key=lambda record: record.dcc_number)
        except ValueError:
            raise FileNotFoundError(
                f"No locally archived records exist for {dcc_number}."
            )

    def document_dir(self, dcc_number):
        """The directory in the local archive of the document corresponding to the
        specified DCC number.

        This directory contains subdirectories corresponding to revisions (versions) of
        the document, and may not yet exist.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number. If a version is specified, it is ignored.

        Returns
        -------
        :class:`pathlib.Path`
            The directory in the local archive corresponding to the document.
        """
        return self.archive_dir / dcc_number.format(version=False)

    def revision_dir(self, dcc_number):
        """The directory in the local archive of the revision corresponding to the
        specified versioned DCC number.

        This directory is used to store data for a particular version of a DCC record,
        and may not yet exist.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number. Must contain a version.

        Returns
        -------
        :class:`pathlib.Path`
            The directory in the local archive corresponding to the document revision.

        Raises
        ------
        :class:`.NoVersionError`
            If `dcc_number` does not contain a version.
        """
        # We require a version.
        if dcc_number.version is None:
            raise NoVersionError()

        document_path = self.document_dir(dcc_number)
        return document_path / dcc_number.format(version=True)

    def revision_meta_path(self, dcc_number):
        """The path to the meta file in the local archive of the revision corresponding
        to the specified DCC number.

        The meta file may not yet exist.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number. Must contain a version.

        Returns
        -------
        :class:`pathlib.Path`
            The path to the meta file in the local archive corresponding to the document
            revision.

        Raises
        ------
        :class:`.NoVersionError`
            If `dcc_number` does not contain a version.
        """
        return self._meta_path(self.revision_dir(dcc_number))

    def _meta_path(self, directory):
        return directory / "meta.toml"


@dataclass
class DCCAuthor:
    """A DCC author."""

    name: str
    uid: int = None

    def __str__(self):
        return self.name


@dataclass
@total_ordering
class DCCNumber:
    """A DCC number including category and numeric identifier.

    You must either provide a string containing the DCC number, or the separate category
    and numeric parts, with optional version, e.g.:

    >>> from dcc.records import DCCNumber
    >>> DCCNumber("T1234567")
    DCCNumber(category='T', numeric='1234567', version=None)
    >>> DCCNumber("T", "1234567")
    DCCNumber(category='T', numeric='1234567', version=None)
    >>> DCCNumber("T", "1234567", 4)
    DCCNumber(category='T', numeric='1234567', version=4)

    Parameters
    ----------
    category, numeric, version : str, optional
        The parts that make up the DCC number.
    """

    category: str
    numeric: str
    version: int = None

    # DCC document type designators and descriptions.
    document_type_letters = {
        "A": "Acquisitions",
        "C": "Contractual or procurement",
        "D": "Drawings",
        "E": "Engineering documents",
        "F": "Forms and Templates",
        "G": "Presentations (eg Graphics)",
        "L": "Letters and Memos",
        "M": "Management or Policy",
        "P": "Publications",
        "Q": "Quality Assurance documents",
        "R": "Operations Change Requests",
        "S": "Serial numbers",
        "T": "Techical notes",
        "X": "Safety Incident Reports",
    }

    def __init__(self, category, numeric=None, version=None):
        # Copy constructor.
        if isinstance(category, DCCNumber):
            numeric = category.numeric
            try:
                version = int(category.version)
            except TypeError:
                pass
            category = category.category
        elif numeric is None:
            # Full number specified in the first argument. Check it's long enough.
            if len(category) < 2:
                raise ValueError(
                    f"Invalid DCC number {repr(category)}; should be of the form "
                    f"'T0123456'"
                )

            # Get rid of first "LIGO-" if present.
            if category.startswith("LIGO-"):
                category = category[len("LIGO-") :]

            try:
                # Find where the hyphen denoting the version is.
                hyphen_index = category.index("-")
            except ValueError:
                # Couldn't find it.
                hyphen_index = None

            if hyphen_index is not None:
                # Check if the version was specified, and if so, warn the user.
                if version is not None:
                    LOGGER.warning(
                        "Version argument ignored as it was specified in the DCC string"
                    )

                # Numeric part is between second character and index.
                numeric = category[1:hyphen_index]

                # Version is last part, two places beyond start of hyphen.
                version = category[hyphen_index + 2 :]
            else:
                # Numeric is everything after first character.
                numeric = category[1:]

            # Category should be first.
            category = category[0]

        # Check category is valid.
        category = str(category)
        if category not in self.document_type_letters:
            raise ValueError(f"Category {repr(category)} is invalid.")

        # Check number is valid.
        numeric = str(numeric)
        if not numeric.isdigit():
            raise ValueError(f"Number {repr(numeric)} is invalid")

        # Validate version if it was found.
        if version is not None:
            # Check version is valid.
            if not str(version).isdigit():
                raise ValueError(f"Version {repr(version)} is invalid")

            version = int(version)

        self.category = category
        self.numeric = numeric
        self.version = version

    def format(self, version=True):
        """String representation of the DCC number, with optional version number.

        Parameters
        ----------
        version : bool, optional
            Include the version in the string. Defaults to True.

        Returns
        -------
        str
            The string representation.
        """
        version_string = self.version_suffix if version else ""
        return f"{self.category}{self.numeric}{version_string}"

    @property
    def version_suffix(self):
        """The string version suffix for the version number.

        Returns
        -------
        str
            The version suffix to the DCC numeral, e.g. "-v2".
        """
        # Version 0 should end "x0", otherwise "v1" etc.
        if self.version is None:
            return ""
        elif self.version == 0:
            return "-x0"
        else:
            return f"-v{self.version}"

    def __str__(self):
        return self.format(version=True)

    def __eq__(self, other):
        try:
            return all(
                (
                    self.category == other.category,
                    self.numeric == other.numeric,
                    self.version == other.version,
                )
            )
        except Exception:
            return NotImplemented

    def __gt__(self, other):
        if self.version is None or other.version is None:
            return NotImplemented

        return all(
            (
                self.category == other.category,
                self.numeric == other.numeric,
                self.version > other.version,
            )
        )


@dataclass
class DCCFile:
    """A DCC file."""

    title: str
    filename: str
    url: str
    local_path: Path = field(init=False, default=None)

    def __post_init__(self):
        self.title = self.title.strip()
        self.filename = self.filename.strip()

    def __str__(self):
        if self.title == self.filename:
            return self.title

        return f"{self.title} ({self.filename})"

    @ensure_session
    def fetch(self, directory, *, overwrite=False, session):
        """Fetch the remote file and store in the local archive.

        Parameters
        ----------
        directory : str or :class:`pathlib.Path`
            The directory to use to store the file.

        overwrite : bool, optional
            Whether to overwrite any existing file in the archive with that fetched
            remotely. Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        file_path = Path(directory / self.filename)

        if not overwrite and file_path.exists():
            # The file is available in the local archive.
            LOGGER.info(f"{file_path} already exists.")
        else:
            # Fetch the remote file.
            LOGGER.info(f"Fetching {self} from DCC")

            if file_path.exists():
                LOGGER.info(f"Overwriting {file_path}")
            else:
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # First fetch the file from the DCC to a temporary file in the same
            # directory, then move it to the final location, to ensure atomicity.
            # Just create a new file directly (don't use `tempfile`) so that the new
            # temporary file has the target directory's intended mode.
            file_path_tmp = file_path.parent / f".{file_path.name}-tmp"
            with file_path_tmp.open("w+b") as fobj:
                # Get the file contents from the DCC.
                LOGGER.info(f"Downloading {self}")
                for chunk in session.fetch_file_contents(self):
                    fobj.write(chunk)

            # Move to the final location.
            LOGGER.info(f"Saving {self} to {file_path}")
            # NOTE: remove str() for Python >= 3.9.
            shutil.move(str(file_path_tmp), str(file_path))  # Atomic when dirs match.

        self.discover(directory)

    def write(self, path):
        """Write file to the file system.

        Parameters
        ----------
        path : str, :class:`pathlib.Path`, or file-like
            The path or file object to write to. If an open file object is given, it
            will be written to and left open. If a path string is given, it will be
            opened, written to, then closed.
        """
        if self.local_path is None:
            raise FileNotFoundError(f"No known local copy of {self}.")

        # Copy, allowing for open file objects.
        with opened_file(self.local_path, "rb") as src, opened_file(path, "wb") as dst:
            shutil.copyfileobj(src, dst)

    def discover(self, directory):
        """Update local file path if the local file exists in `directory`.

        Parameters
        ----------
        directory : :class:`str` or :class:`pathlib.Path`
            The directory to search.
        """
        path = Path(directory / self.filename)
        if path.is_file():
            LOGGER.debug(f"Discovered {self} local file at {path}.")
            self.local_path = path

    def exists(self):
        """Whether the file exists at the local path.

        Returns
        -------
        :class:`bool`
            True if the file exists at the local path, False otherwise.
        """
        if self.local_path is None:
            return False

        return self.local_path.is_file()


@dataclass
class DCCJournalRef:
    """A DCC record journal reference."""

    journal: str
    volume: int
    page: str  # Not necessarily numeric!
    citation: str
    url: str = None  # Not always present, e.g. P000011

    def __str__(self):
        journal = self.journal if self.journal else "Unknown journal"
        volume = self.volume if self.volume else "?"
        page = self.page if self.page else "?"
        url = f" ({self.url})" if self.url else ""

        return f"{journal} vol. {volume}, pg. {page}{url}"


@dataclass
class DCCRecord:
    """A DCC record."""

    dcc_number: DCCNumber
    title: str = None
    authors: List[DCCAuthor] = None
    abstract: str = None
    keywords: List[str] = None
    note: str = None
    publication_info: str = None
    journal_reference: DCCJournalRef = None
    other_versions: List[int] = None
    creation_date: datetime.datetime = None
    contents_revision_date: datetime.datetime = None
    metadata_revision_date: datetime.datetime = None
    files: List[DCCFile] = None
    referenced_by: List[DCCNumber] = None
    related_to: List[DCCNumber] = None

    def __str__(self):
        return f"{self.dcc_number}: {repr(self.title)}"

    def __post_init__(self):
        self.dcc_number = DCCNumber(self.dcc_number)
        ## Lists have to be lists, for serialisation support.
        self.authors = list(self.authors or [])
        self.other_versions = list(self.other_versions or [])
        self.files = list(self.files or [])
        # Ensure referencing documents don't include this one.
        pred = lambda number: number.numeric != self.dcc_number.numeric
        self.referenced_by = list(takewhile(pred, self.referenced_by or []))
        self.related_to = list(takewhile(pred, self.related_to or []))

    @classmethod
    @ensure_session
    def fetch(cls, dcc_number, *, session):
        """Fetch record from the remote DCC host.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC record to fetch.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Returns
        -------
        :class:`.DCCRecord`
            The fetched record.
        """
        dcc_number = DCCNumber(dcc_number)

        # Get the document contents from the DCC.
        response = session.fetch_record_page(dcc_number)

        # Parse the document.
        parsed = DCCXMLRecordParser(response.text)
        parsed_dcc_number = DCCNumber(*parsed.dcc_number_pieces)

        # Make sure the record matches the request.
        if any(
            (
                parsed_dcc_number.category != dcc_number.category,
                parsed_dcc_number.numeric != dcc_number.numeric,
            )
        ):
            raise ValueError(
                f"The retrieved record, {parsed_dcc_number}, is different from the "
                f"requested one, {dcc_number}."
            )
        elif (
            dcc_number.version is not None
            and parsed_dcc_number.version != dcc_number.version
        ):
            # Correct document number, but incorrect version.
            raise ValueError(
                f"The retrieved record, {parsed_dcc_number}, has a different version "
                f"to the requested one, {dcc_number}"
            )

        if parsed.journal_reference is not None:
            journal_reference = DCCJournalRef(*parsed.journal_reference)
        else:
            journal_reference = None

        # Remove the current version from the parsed versions.
        other_versions = set(parsed.other_version_numbers)
        try:
            other_versions.remove(parsed_dcc_number.version)
        except KeyError:
            pass

        creation_date, contents_rev_date, metadata_rev_date = parsed.revision_dates

        files = [DCCFile(*file_) for file_ in parsed.attached_files]

        return DCCRecord(
            dcc_number=parsed_dcc_number,
            title=parsed.title,
            authors=[DCCAuthor(name, uid) for name, uid in parsed.authors],
            abstract=parsed.abstract,
            keywords=parsed.keywords,
            note=parsed.note,
            publication_info=parsed.publication_info,
            journal_reference=journal_reference,
            other_versions=other_versions,
            creation_date=creation_date,
            contents_revision_date=contents_rev_date,
            metadata_revision_date=metadata_rev_date,
            files=files,
            referenced_by=[DCCNumber(ref) for ref in parsed.referencing_ids],
            related_to=[DCCNumber(ref) for ref in parsed.related_ids],
        )

    def discover_files(self, directory):
        """Discover existing files in `directory` corresponding to this record.

        Parameters
        ----------
        directory : :class:`str` or :class:`pathlib.Path`
            The directory to search.
        """
        for file_ in self.files:
            file_.discover(directory)

    @ensure_session
    def fetch_files(
        self, directory, *, ignore_too_large=False, overwrite=False, session
    ):
        """Fetch files attached to this record.

        Parameters
        ----------
        directory : str or :class:`pathlib.Path`
            The directory in which to store the fetched files.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a
            :class:`.TooLargeFileSkippedException`. If True, the file is simply ignored.

        overwrite : bool, optional
            Whether to overwrite existing local files with those fetched remotely.
            Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Returns
        -------
        list
            The fetched :class:`files <.DCCFile>`.
        """
        files = []
        for index in range(len(self.files)):
            files.append(
                self.fetch_file(
                    index + 1,
                    directory,
                    ignore_too_large=ignore_too_large,
                    overwrite=overwrite,
                    session=session,
                )
            )

        return files

    @ensure_session
    def fetch_file(
        self, number, directory, *, ignore_too_large=False, overwrite=False, session
    ):
        """Fetch file attached to this record.

        Parameters
        ----------
        number : int
            The file number to fetch.

        directory : str or :class:`pathlib.Path`
            The directory in which to store the fetched file.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a
            :class:`.TooLargeFileSkippedException`. If True, the file is simply ignored.

        overwrite : bool, optional
            Whether to overwrite the existing local file with that fetched remotely.
            Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Returns
        -------
        :class:`.DCCFile`
            The fetched file.
        """
        file_ = self.files[number - 1]
        LOGGER.debug(f"Fetching {file_} contents.")

        try:
            file_.fetch(directory, overwrite=overwrite, session=session)
        except TooLargeFileSkippedException as err:
            if ignore_too_large:
                # Just skip the file, don't raise the error.
                LOGGER.debug(f"{err}; skipping")
            else:
                raise

        return file_

    @ensure_session
    def update(self, *, session):
        """Update the remote record metadata.

        Parameters
        ----------
        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        # Get the document contents from the DCC.
        response = session.update_record_metadata(self)

        # Parse the document (exceptions to be handled by calling code).
        DCCXMLUpdateParser(response.text)

    def write(self, path):
        """Write record to the file system.

        Parameters
        ----------
        path : str, :class:`pathlib.Path`, or file-like
            The path or file object to write to. If an open file object is given, it
            will be written to and left open. If a path string is given, it will be
            opened, written to, then closed.
        """
        # Create a metadata dict.
        item = dict(__schema__="1")  # Do this first so it's at the top of the file.
        itemdict = asdict(self)
        # Strip out None values, which TOML can't serialise.
        itemdict = remove_none(itemdict)
        item.update(itemdict)

        # Apply some corrections.
        for number, file_ in enumerate(item["files"]):
            # Remove fields that can be reproduced from other data.
            file_.pop("local_path", None)

        with opened_file(path, "wb") as fobj:
            tomli_w.dump(item, fobj, multiline_strings=True)

        # Verification: check the file can be parsed again.
        assert self.read(path)

    @classmethod
    def read(cls, path):
        """Read record from the file system.

        Parameters
        ----------
        path : str or :class:`pathlib.Path`
            The path for the record's meta file.

        Returns
        -------
        :class:`.DCCRecord`
            The record.
        """
        path = Path(path)

        with path.open("rb") as fobj:
            LOGGER.debug(f"Reading metadata from {path}.")
            item = tomli.load(fobj)

        # Check the file came from us.
        assert item["__schema__"] == "1", "Unsupported schema"
        item.pop("__schema__", None)

        item["dcc_number"] = DCCNumber(**item["dcc_number"])
        if "authors" in item:
            item["authors"] = [DCCAuthor(**author) for author in item["authors"]]
        if "journal_reference" in item:
            item["journal_reference"] = DCCJournalRef(**item["journal_reference"])
        if "files" in item:
            files = []
            for filedata in item["files"]:
                file_ = DCCFile(**filedata)

                # Update local path if the file has been downloaded.
                local_path = path.parent / file_.filename
                if local_path.is_file():
                    file_.local_path = local_path

                files.append(file_)
            item["files"] = files
        if "referenced_by" in item:
            item["referenced_by"] = [DCCNumber(**ref) for ref in item["referenced_by"]]
        if "related_to" in item:
            item["related_to"] = [DCCNumber(**ref) for ref in item["related_to"]]

        return DCCRecord(**item)

    @property
    def author_names(self):
        """The names of the authors associated with this record.

        Returns
        -------
        :class:`list`
            The author names.
        """

        return [author.name for author in self.authors]

    @property
    def version_numbers(self):
        """The versions associated with this record.

        Returns
        -------
        :class:`set`
            The versions.
        """

        return set([self.dcc_number.version, *self.other_versions])

    @property
    def filenames(self):
        """The filenames associated with this record.

        Returns
        -------
        :class:`list`
            The filenames.
        """

        return [str(file_) for file_ in self.files]

    @property
    def latest_version_number(self):
        """The latest version number for this record.

        Returns
        -------
        :class:`int`
            The latest version number.
        """

        return max(self.version_numbers)

    def is_latest_version(self):
        """Check if the current record is the latest version.

        Note: this only checks the current record instance represents the latest known
        local record. The remote record is not fetched.

        Returns
        -------
        :class:`bool`
            True if the current version is the latest; False otherwise.
        """
        return self.dcc_number.version is self.latest_version_number

    def refenced_by_titles(self):
        """The titles of the records referencing this record.

        Returns
        -------
        :class:`list`
            The titles.
        """
        return [str(record) for record in self.referenced_by]

    def related_titles(self):
        """The titles of the records related to this record.

        Returns
        -------
        :class:`list`
            The titles.
        """
        return [str(record) for record in self.related]
