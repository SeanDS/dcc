"""Record objects."""

import logging
from typing import List
from pathlib import Path
import shutil
from dataclasses import dataclass, field, asdict
from itertools import takewhile
from functools import total_ordering, wraps
from tempfile import TemporaryFile
import datetime
import tomli
import tomli_w
from .sessions import DCCSession
from .parsers import DCCXMLRecordParser, DCCXMLUpdateParser
from .util import opened_file, remove_none
from .env import DEFAULT_HOST, DEFAULT_IDP
from .exceptions import NoVersionError, FileTooLargeError

LOGGER = logging.getLogger(__name__)


def ensure_session(func):
    """Ensure the `session` argument passed to the wrapped function is real, creating a
    temporary session if required."""

    @wraps(func)
    def wrapped(*args, session=None, **kwargs):
        if session is None:
            LOGGER.debug(f"Using default session for called {func}.")
            with DCCSession(DEFAULT_HOST, DEFAULT_IDP) as session:
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

    def records(self):
        """Records in the local archive.

        Yields
        ------
        :class:`.DCCRecord`
            The latest version of a record in the archive.
        """
        for path in self.archive_dir.iterdir():
            if not path.is_dir():
                continue

            yield from self.document_records(path.name)

    @ensure_session
    def fetch_record(
        self,
        dcc_number,
        *,
        prefer_local_archive=False,
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

        prefer_local_archive : bool, optional
            Whether to prefer the archive over fetching latest remote records. Defaults
            to False.

        overwrite : bool, optional
            Whether to overwrite existing records and files in the archive with those
            fetched remotely. Defaults to False.

        fetch_files : bool, optional
            Whether to also fetch the files attached to the record. Defaults to False.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a :class:`.FileTooLargeError`. If
            True, the file is simply ignored.

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

            if prefer_local_archive:
                # Use the latest archived record, if found.
                LOGGER.info(
                    "Searching for latest record in the local archive (disable by "
                    "setting prefer_local_archive to False)."
                )
                try:
                    record = self.latest_record(dcc_number)
                except FileNotFoundError:
                    LOGGER.info("No locally archived record of any version exists.")
                else:
                    LOGGER.info("Found record in local archive.")
            else:
                # We can't know for sure that the local archive contains the latest
                # version, so we have to fetch the remote.
                LOGGER.info(
                    "Ignoring local archive (disable by setting "
                    "DCCArchive.prefer_local_archive to True)."
                )
        else:
            if not overwrite:
                meta_file = self.record_meta_path(dcc_number)

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

            # Store/update record in the local archive.
            self.archive_record_metadata(record, overwrite=overwrite)

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
        """Fetch a DCC record, either from the local archive or from the remote DCC
        host, adding it to the local archive if necessary.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to fetch files for.

        ignore_too_large : bool, optional
            If False, when a file is too large, raise a :class:`.FileTooLargeError`. If
            True, the file is simply ignored.

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
            self.record_dir(record.dcc_number),
            ignore_too_large=ignore_too_large,
            overwrite=overwrite,
            session=session,
        )

    @ensure_session
    def fetch_record_file(self, record, number, *, overwrite=False, session):
        """Fetch a DCC record, either from the local archive or from the remote DCC
        host, adding it to the local archive if necessary.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to fetch files for.

        number : int
            The file number to fetch.

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
            self.record_dir(record.dcc_number),
            overwrite=overwrite,
            session=session,
        )

    def archive_record_metadata(self, record, *, overwrite=False):
        """Serialise record metadata in the local archive.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record to archive.

        overwrite : bool, optional
            Whether to overwrite any existing record in the local archive. Defaults to
            False.
        """
        meta_path = self.record_meta_path(record.dcc_number)

        if meta_path.is_file():
            if not overwrite:
                LOGGER.info(
                    f"Refusing to overwrite existing meta file at {meta_path}; set "
                    f"overwrite to force."
                )
                return

            LOGGER.info(f"Overwriting {meta_path}")

        LOGGER.info(f"Archiving {record} metadata to {meta_path}")
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        record.write(meta_path)

    def document_records(self, dcc_number):
        """Load all DCC records for a given DCC number from the local archive.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC number to load records for (if present, the version is ignored).

        Returns
        -------
        :class:`list`
            The :class:`records <.DCCRecord>` corresponding to `dcc_number` in the local
            archive.
        """
        dcc_number = DCCNumber(dcc_number)
        document_dir = self.document_dir(dcc_number)

        records = []

        if document_dir.exists():
            for path in document_dir.iterdir():
                if not path.is_dir():
                    continue

                # Parse the record if exists.
                records.append(DCCRecord.read(self._meta_path(path)))

        return records

    def latest_record(self, dcc_number):
        """Load the latest DCC record from the local archive.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC number to load the latest record for (if present, the version is
            ignored).

        Returns
        -------
        :class:`.DCCRecord`
            The latest record corresponding to `dcc_number` in the local archive.

        Raises
        ------
        :class:`FileNotFoundError`
            If no records matching `dcc_number` exist in the local archive.
        """
        records = self.document_records(dcc_number)
        try:
            # Return the record with the latest version.
            return max(records, key=lambda record: record.dcc_number)
        except ValueError:
            raise FileNotFoundError(
                f"No locally archived records exist for {dcc_number}."
            )

    def document_dir(self, dcc_number):
        """The local archive directory for the specified DCC number, without a
        particular version.

        This directory is used to store versioned records.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number.

        Returns
        -------
        :class:`pathlib.Path`
            The document's directory in the local archive.
        """
        return self.archive_dir / dcc_number.string_repr(version=False)

    def record_dir(self, dcc_number):
        """The local archive directory for the specified DCC number, with a particular
        version.

        This directory is used to store data for a particular version of a DCC record.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number.

        Returns
        -------
        :class:`pathlib.Path`
            The record's directory in the local archive.
        """
        # We require a version.
        if dcc_number.version is None:
            raise NoVersionError()

        document_path = self.document_dir(dcc_number)
        return document_path / dcc_number.string_repr(version=True)

    def record_meta_path(self, dcc_number):
        """The meta file in the local archive for the specified DCC number.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC number.

        Returns
        -------
        :class:`pathlib.Path`
            The record's meta file path in the local archive.
        """
        return self._meta_path(self.record_dir(dcc_number))

    def _meta_path(self, directory):
        return directory / "meta.toml"


@dataclass
class DCCAuthor:
    """A DCC author."""

    name: str
    uid: int = None

    def __str__(self):
        return f"{self.name} (id {self.uid})"


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
        "R": "__unknown__",  # Exists (e.g. M1700260 XML) but not public.
        "S": "Serial numbers",
        "T": "Techical notes",
        "X": "__unknown__",  # Exists (e.g. T1100286 XML) but not public.
    }

    def __init__(self, category, numeric=None, version=None):
        # Copy constructor.
        if isinstance(category, DCCNumber):
            numeric = str(category.numeric)
            try:
                version = int(category.version)
            except TypeError:
                pass
            category = str(category.category)
        elif numeric is None:
            # Full number specified in the first argument. Check it's long enough.
            if len(category) < 2:
                raise ValueError("Invalid DCC number; should be of the form 'T0123456'")

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
                numeric = str(category[1:hyphen_index])

                # Version is last part, two places beyond start of hyphen.
                version = int(category[hyphen_index + 2 :])
            else:
                # Numeric is everything after first character.
                numeric = str(category[1:])

            # Category should be first.
            category = str(category[0])
        else:
            # Category is the first argument.
            category = str(category)

        # Check category is valid.
        if not DCCNumber.is_valid_category(category):
            raise ValueError(f"Category {repr(category)} is invalid.")

        # Check number is valid.
        if not DCCNumber.is_valid_numeric(numeric):
            raise ValueError(f"Number {repr(numeric)} is invalid")

        # Validate version if it was found.
        if version is not None:
            version = int(version)

            # Check version is valid.
            if not DCCNumber.is_valid_version(version):
                raise ValueError(f"Version {repr(version)} is invalid")

        self.category = category
        self.numeric = numeric
        self.version = version

    @classmethod
    def is_valid_category(cls, letter):
        """Check if the specified category letter is valid.

        Parameters
        ----------
        letter : str
            The category letter to check.

        Returns
        -------
        bool
            True if the category letter is valid; False otherwise.
        """
        return letter in cls.document_type_letters

    @staticmethod
    def is_valid_numeric(numeral):
        """Check if the specified number is a valid DCC numeral.

        Parameters
        ----------
        numeral : str
            The DCC numeral to check.

        Returns
        -------
        bool
            True if the numeral is valid; False otherwise.
        """
        return int(numeral) > 0

    @staticmethod
    def is_valid_version(version):
        """Check if the specified version number is valid.

        Parameters
        ----------
        version : int
            The version to check.

        Returns
        -------
        bool
            True if the version is valid; False otherwise.
        """
        return int(version) >= 0

    def numbers_equal(self, other):
        """Check if the category and numeric parts of this number and the specified one
        match.

        Parameters
        ----------
        other : :class:`.DCCNumber`
            The other DCC number to check.

        Returns
        -------
        bool
            True if the other number and category match; False otherwise.
        """
        return other.category == self.category and other.numeric == self.numeric

    def string_repr(self, version=True):
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
        return self.string_repr(version=True)

    def __eq__(self, other):
        try:
            # Compare the category, number and version.
            return self.numbers_equal(other) and other.version == self.version
        except Exception:
            return NotImplemented

    def __gt__(self, other):
        if (
            not self.numbers_equal(other)
            or self.version is None
            or other.version is None
        ):
            return NotImplemented

        return self.version > other.version


@dataclass
class DCCFile:
    """A DCC file."""

    title: str
    filename: str
    url: str
    local_path: Path = field(init=False, default=None)

    def __str__(self):
        return f"{repr(self.title)} ({self.filename})"

    @ensure_session
    def fetch(self, file_path, *, overwrite=False, session):
        """Fetch the remote file and store in the local archive.

        Parameters
        ----------
        file_path : str or :class:`pathlib.Path`
            The path to use to store the file.

        overwrite : bool, optional
            Whether to overwrite any existing file in the archive with that fetched
            remotely. Defaults to False.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        file_path = Path(file_path)

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

            # Fetch the file from the DCC. First download it to a temporary file, then
            # move it to the final location if the download was successful. This ensures
            # interrupted downloads don't leave partially downloaded (corrupt) files in
            # the archive.
            with TemporaryFile("w+b") as src:
                # Get the file contents from the DCC.
                LOGGER.info(f"Downloading {self}")
                for chunk in session.fetch_file_contents(self):
                    src.write(chunk)

                # Rewind the file so the copy below takes the whole file.
                src.seek(0)

                LOGGER.info(f"Saving {self} to {file_path}")
                with file_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

                self.local_path = file_path

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
            raise FileNotFoundError(
                f"Local copy of {self} not found (run "
                f"{self.__class__.__name__}.fetch())."
            )

        # Copy, allowing for open file objects.
        with opened_file(self.local_path, "rb") as src, opened_file(path, "wb") as dst:
            shutil.copyfileobj(src, dst)


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
    other_versions: List[DCCNumber] = None
    creation_date: datetime.datetime = None
    contents_revision_date: datetime.datetime = None
    metadata_revision_date: datetime.datetime = None
    files: List[DCCFile] = None
    referenced_by: List[DCCNumber] = None
    related_to: List[DCCNumber] = None

    def __str__(self):
        return f"{self.dcc_number}: {repr(self.title)}"

    def __post_init__(self):
        ## Lists have to be lists, for serialisation support.
        self.authors = list(self.authors)
        self.other_versions = list(self.other_versions)
        self.files = list(self.files)
        # Ensure referencing documents don't include this one.
        pred = lambda number: number.numeric != self.dcc_number.numeric
        self.referenced_by = list(takewhile(pred, self.referenced_by))
        self.related_to = list(takewhile(pred, self.related_to))

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
        if not parsed_dcc_number.numbers_equal(dcc_number):
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
            If False, when a file is too large, raise a :class:`.FileTooLargeError`. If
            True, the file is simply ignored.

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
        for number in range(1, len(self.files) + 1):
            try:
                file_ = self.fetch_file(
                    number, directory, overwrite=overwrite, session=session
                )
            except FileTooLargeError as err:
                if ignore_too_large:
                    # Just skip the file, don't raise the error.
                    LOGGER.debug(f"{err}; skipping")
                else:
                    raise
            else:
                files.append(file_)

        return files

    @ensure_session
    def fetch_file(self, number, directory, *, overwrite=False, session):
        """Fetch file attached to this record.

        Parameters
        ----------
        number : int
            The file number to fetch.

        directory : str or :class:`pathlib.Path`
            The directory in which to store the fetched file.

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
        path = Path(directory) / file_.filename
        LOGGER.debug(f"Fetching {file_} contents.")
        file_.fetch(path, overwrite=overwrite, session=session)
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
        :class:`list`
            The versions.
        """

        versions = set(self.other_versions)
        versions.add(self.dcc_number.version)

        return versions

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

        # find highest other version
        max_other_version = max(self.other_versions)

        # check if this is greater than the current version
        if max_other_version > self.dcc_number.version:
            return max_other_version

        return self.dcc_number.version

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
