"""Record objects."""

import logging
from typing import List
from pathlib import Path
import shutil
from dataclasses import dataclass, field, asdict
from itertools import takewhile
from functools import total_ordering
import datetime
import click
import toml
from .sessions import DCCSession
from .parsers import DCCXMLRecordParser, DCCXMLUpdateParser
from .util import opened_file
from .env import DEFAULT_HOST, DEFAULT_IDP

LOGGER = logging.getLogger(__name__)


def _default_session():
    return DCCSession(DEFAULT_HOST, DEFAULT_IDP)


class DCCArchive:
    """A collection of DCC documents."""

    def records(self, session=None):
        """Records in the archive.

        Parameters
        ----------
        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.

        Yields
        ------
        :class:`.DCCRecord`
            The latest version of a record in the archive.
        """
        if session is None:
            with _default_session() as session:
                return self.records(session=session)

        for path in session.archive_dir.iterdir():
            if not path.is_dir():
                continue

            # Try to parse document.
            try:
                yield self.fetch_latest_record(path.name, session=session)
            except Exception as e:
                print(e)
                # Not a valid document directory, or empty.
                pass

    def fetch_record(self, dcc_number, fetch_files=False, session=None):
        """Fetch a DCC record and adds it to the archive.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC record to fetch.

        fetch_files : bool, optional
            Whether to also fetch the files attached to the record.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return self.fetch_record(
                    dcc_number=dcc_number, fetch_files=fetch_files, session=session
                )

        dcc_number = DCCNumber(dcc_number)

        # Fetch record.
        record = DCCRecord.fetch(dcc_number, session=session)

        if fetch_files:
            record.fetch_files(session=session)

        return record

    @classmethod
    def fetch_latest_record(cls, dcc_number, session=None):
        """Fetch the latest DCC record from the archive.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber` or str
            The DCC record to fetch.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return cls.fetch_latest_record(dcc_number=dcc_number, session=session)

        dcc_number = DCCNumber(dcc_number)
        document_dir = session.document_archive_dir(dcc_number)

        if document_dir.exists():
            records = []

            for path in document_dir.iterdir():
                if not path.is_dir():
                    continue

                # Try to parse as a record.
                try:
                    records.append(DCCRecord.read(path))
                except Exception:
                    pass

            if records:
                # Return the record with the latest version.
                return max(records, key=lambda record: record.dcc_number)

        raise FileNotFoundError(f"No archived record exists for {dcc_number}.")


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
        "R": "__unknown__",  # Exists (in XML of e.g. M1700260), but not in forms?
        "S": "Serial numbers",
        "T": "Techical notes",
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
        if not DCCNumber.is_category_letter(category):
            raise ValueError(f"Category {repr(category)} is invalid.")

        # Check number is valid.
        if not DCCNumber.is_dcc_numeric(numeric):
            raise ValueError(f"Number {repr(numeric)} is invalid")

        # Validate version if it was found.
        if version is not None:
            version = int(version)

            # Check version is valid.
            if not DCCNumber.is_dcc_version(version):
                raise ValueError(f"Version {repr(version)} is invalid")

        self.category = category
        self.numeric = numeric
        self.version = version

    def open(self, session=None, xml=False):
        """Open the DCC record in the user's browser."""
        if session is None:
            with _default_session() as session:
                return self.open(session=session, xml=xml)

        url = session.dcc_record_url(self, xml=xml)
        click.launch(url)

    @classmethod
    def is_category_letter(cls, letter):
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
    def is_dcc_numeric(numeral):
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

    def has_version(self):
        """Check if the DCC number has a version associated with it."""
        return self.version is not None

    @staticmethod
    def is_dcc_version(version):
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

    @property
    def version_suffix(self):
        """The string version suffix for the version number.

        Returns
        -------
        str
            The version suffix to the DCC numeral, e.g. "-v2".
        """
        # Version 0 should end "x0", otherwise "v1" etc.
        if not self.has_version():
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
            or not self.has_version()
            or not other.has_version
        ):
            return NotImplemented

        return self.version > other.version


@dataclass
class DCCFile:
    """A DCC file."""

    title: str
    filename: Path
    url: str
    local_path: Path = field(init=False, default=None)

    def __post_init__(self):
        self.filename = Path(self.filename)

    def __str__(self):
        return f"{repr(self.title)} ({self.filename})"

    def fetch_file_contents(self, record, session=None):
        """Fetch the remote file's contents.

        Parameters
        ----------
        record : :class:`.DCCRecord`
            The record associated with this file.

        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return self.fetch_file_contents(record=record, session=session)

        self.local_path = session.file_archive_path(record, self)

        if not session.overwrite and self.local_path.exists():
            # The file is available in the local archive.
            LOGGER.info(f"{self} is already present in the local archive")
        else:
            # Fetch the remote file.
            LOGGER.info(f"Fetching {self} from DCC")

            if self.local_path.exists():
                LOGGER.info(f"Overwriting {self.local_path}")
            else:
                self.local_path.parent.mkdir(parents=True, exist_ok=True)

            # Get the file contents from the DCC.
            with self.local_path.open("wb") as fobj:
                LOGGER.info(f"Archiving {self} at {self.local_path}")
                for chunk in session.fetch_file_contents(self):
                    fobj.write(chunk)

    def open(self):
        """Open the file using the operating system."""
        if self.local_path is None:
            raise FileNotFoundError(
                f"Local copy of {self} has not yet been archived (run "
                f"{self.__class__.__name__}.fetch_file_contents())."
            )

        click.launch(str(self.local_path))

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
                f"Local copy of {self} has not yet been archived (run "
                f"{self.__class__.__name__}.fetch_file_contents())."
            )

        # Copy, allowing for open file objects.
        with opened_file(self.local_path, "rb") as src, opened_file(path, "wb") as dest:
            shutil.copyfileobj(src, dest)


@dataclass
class DCCJournalRef:
    """A DCC record journal reference."""

    journal: str
    volume: int
    page: str  # Not necessarily numeric!
    citation: str
    url: str

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
        return f"{self.dcc_number}: {self.title}"

    def __post_init__(self):
        # Ensure referencing documents don't include this one.
        pred = lambda number: number.numeric != self.dcc_number.numeric
        self.referenced_by = list(takewhile(pred, self.referenced_by))
        self.related_to = list(takewhile(pred, self.related_to))

    @classmethod
    def fetch(cls, dcc_number, session=None):
        """Fetch and create a DCC record.

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
        if session is None:
            with _default_session() as session:
                return cls.fetch(dcc_number, session=session)

        dcc_number = DCCNumber(dcc_number)

        if not dcc_number.has_version():
            LOGGER.info(
                f"No version specified in requested record {repr(str(dcc_number))}."
            )

            if session.prefer_archive:
                # Use the latest archived record, if found.
                LOGGER.info(
                    "Attempting to fetch latest archived record (disable by unsetting "
                    "session's prefer_archive flag)."
                )
                try:
                    return DCCArchive.fetch_latest_record(dcc_number, session=session)
                except FileNotFoundError:
                    LOGGER.info("No archived record of any version exists.")
            else:
                # We can't know for sure that the local archive contains the latest
                # version, so we have to fetch the remote.
                LOGGER.info(
                    "Ignoring archive (disable by setting session's prefer_archive "
                    "flag)."
                )
        else:
            if not session.overwrite:
                cache_dir = session.record_archive_dir(dcc_number)

                if cache_dir.exists():
                    # Retrieve the cached record.
                    LOGGER.info(f"Fetching {dcc_number} from the local archive")

                    try:
                        return cls.read(cache_dir)
                    except FileNotFoundError as err:
                        raise Exception(f"{err} (document in archive corrupt?)")
            else:
                LOGGER.info(f"Overwriting archived copy of {dcc_number} if present")

        # Fetch the remote record.
        LOGGER.info(f"Fetching {dcc_number} from DCC")
        record = cls._fetch_remote(dcc_number, session)

        # Archive if required.
        record.archive(session=session)

        return record

    @classmethod
    def _fetch_remote(cls, dcc_number, session):
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

    def fetch_files(self, session=None):
        """Fetch files attached to this record.

        Parameters
        ----------
        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return self.fetch_files(session=session)

        for file_ in self.files:
            file_.fetch_file_contents(record=self, session=session)

    def archive(self, session=None):
        """Serialise the record in the local archive.

        Parameters
        ----------
        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return self.archive(session=session)

        archive_dir = session.record_archive_dir(self.dcc_number)
        archive_dir.mkdir(parents=True, exist_ok=True)
        meta_file = self._meta_file(archive_dir)

        if session.overwrite or not meta_file.exists():
            if meta_file.exists():
                LOGGER.info(f"Overwriting {meta_file}")

            LOGGER.info(f"Archiving {self} metadata to {meta_file}")
            self.write(meta_file)
        else:
            # Only reached if the user fetched a record number without a version,
            # but the version retrieved from the DCC already existed in the local
            # archive.
            LOGGER.info(
                f"Refusing to overwrite existing file at {meta_file}; set "
                f"session overwrite flag to force"
            )

    def update(self, session=None):
        """Update the remote record metadata.

        Parameters
        ----------
        session : :class:`.DCCSession`, optional
            The DCC session to use. Defaults to None, which triggers use of the default
            session settings.
        """
        if session is None:
            with _default_session() as session:
                return self.update(session=session)

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
        item = dict(__schema__="1.0.0")  # Do this first so it's at the top of the file.
        item.update(asdict(self))

        # Apply some corrections.
        for file_ in item.get("files", []):
            if "filename" in file_:
                # Only take the string.
                file_["filename"] = str(file_["filename"])

        with opened_file(path, "w") as fobj:
            toml.dump(item, fobj)

    @classmethod
    def read(cls, target_dir):
        """Read record from the file system.

        Parameters
        ----------
        target_dir : str or :class:`pathlib.Path`
            The path to read from.

        Returns
        -------
        :class:`.DCCRecord`
            The record.
        """
        meta_file = cls._meta_file(target_dir)
        with meta_file.open("r") as fobj:
            LOGGER.debug(f"Reading metadata from {meta_file}.")
            item = toml.load(fobj)

        del item["__schema__"]

        item["dcc_number"] = DCCNumber(**item["dcc_number"])
        if "authors" in item:
            item["authors"] = [DCCAuthor(**author) for author in item["authors"]]
        if "journal_reference" in item:
            item["journal_reference"] = DCCJournalRef(**item["journal_reference"])
        if "files" in item:
            item["files"] = [DCCFile(**filedata) for filedata in item["files"]]
        if "referenced_by" in item:
            item["referenced_by"] = [DCCNumber(**ref) for ref in item["referenced_by"]]
        if "related_to" in item:
            item["related_to"] = [DCCNumber(**ref) for ref in item["related_to"]]

        return DCCRecord(**item)

    @staticmethod
    def _meta_file(target_dir):
        return Path(target_dir) / "meta.toml"

    @property
    def author_names(self):
        """The names of the authors associated with this record.

        Returns
        -------
        list
            The author names.
        """

        return [author.name for author in self.authors]

    @property
    def version_numbers(self):
        """The versions associated with this record.

        Returns
        -------
        list
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
        list
            The filenames.
        """

        return [str(file_) for file_ in self.files]

    @property
    def latest_version_number(self):
        """The latest version number for this record.

        Returns
        -------
        int
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
        bool
            True if the current version is the latest; False otherwise.
        """
        return self.dcc_number.version is self.latest_version_number

    def refenced_by_titles(self):
        """The titles of the records referencing this record.

        Returns
        -------
        list
            The titles.
        """
        return [str(record) for record in self.referenced_by]

    def related_titles(self):
        """The titles of the records related to this record.

        Returns
        -------
        list
            The titles.
        """
        return [str(record) for record in self.related]
