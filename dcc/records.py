"""Record objects."""

import logging
from typing import List
from pathlib import Path
import shutil
from dataclasses import dataclass, field
import datetime
from tempfile import NamedTemporaryFile
import click
from .sessions import DCCSession
from .parsers import DCCRecordParser
from .util import opened_file
from .env import DEFAULT_HOST, DEFAULT_IDP

LOGGER = logging.getLogger(__name__)


class DCCArchive:
    """A collection of DCC documents."""

    def __init__(self):
        self.records = {}

    def __str__(self):
        return f"Archive containing {len(self.records)} record(s)"

    def fetch_record(self, dcc_number, overwrite=False, fetch_files=False, **kwargs):
        """Fetches a DCC record and adds it to the archive.

        :param overwrite: whether to force a new download even if the record is in the cache
        :param fetch_files: whether to download the files attached to the record
        """
        dcc_number = DCCNumber(dcc_number)
        key = self._record_key(dcc_number)

        if not overwrite and key in self.records:
            record = self.records[key]
        else:
            # Fetch remote record.
            record = DCCRecord.fetch(dcc_number, **kwargs)

            # Add record to archive.
            self.add_record(record, overwrite=overwrite)

        # Download the files associated with the record, if requested.
        if fetch_files and not record.files_fetched:
            record.fetch_files()

        return record

    def add_record(self, record, overwrite=False):
        """Adds the specified record to the archive.

        :param record: record to add
        :param overwrite: whether to overwrite an existing record
        """
        key = self._record_key(record.dcc_number)

        # Check if record already exists.
        if key in self.records:
            if not overwrite:
                raise RecordCannotBeOverwrittenException()

            LOGGER.info(f"Overwriting existing entry {repr(key)}")

        self.records[key] = record

    def has_record(self, dcc_number):
        """Works out if the specified DCC number or document ID exists in the archive.

        The identifier specified can either be a string or a DCCNumber object,
        but it must contain a version number. For non-versioned searches, use
        has_document.

        :param dcc_number: identifier to check, either a string or a DCCNumber
        """
        dcc_number = DCCNumber(dcc_number)
        return self._record_key(dcc_number) in self.records

    def has_document(self, dcc_number):
        """Checks if the archive contains any version of the specified identifier.

        This is less efficient than has_record.

        :param dcc_number: identifier to check, either a string or a DCCNumber
        """
        dcc_number = DCCNumber(dcc_number)

        # If a version is present, tell the user it is being ignored
        if dcc_number.has_version():
            LOGGER.info(f"Ignoring version number in search for {dcc_number}")

        # Get the DCC number without version suffix.
        search_key = dcc_number.string_repr(version=False)

        for number, record in self.records.items():
            # parse a DCC number from the key
            this_number = DCCNumber(number)

            # check if the strings match
            if this_number.string_repr(version=False) == search_key:
                # Found a match.
                return True

        return False

    @staticmethod
    def _record_key(dcc_number):
        """Creates a string representing the specified DCC number."""
        # We require a version.
        if not dcc_number.has_version():
            raise NoVersionSpecifiedException()

        return dcc_number.string_repr(version=True)


@dataclass
class DCCAuthor:
    """A DCC author."""

    name: str
    uid: int = None

    def __str__(self):
        return f"{self.name} (id {self.uid})"


@dataclass
class DCCNumber:
    """A DCC number including category and numeric identifier.

    You must either provide a string containing the DCC number, or the separate category
    and numeric parts, with optional version, e.g.

        __init__("T1234567")
        __init__("T", "0123456") # equivalent to T0123456
        __init__("T", "0123456", 4) # equivalent to T0123456-v4

    :param first_id: category character, or the full DCC number
    :param numeric: numeric designator of DCC document
    :param version: version number of DCC document
    """

    category: str
    numeric: str
    version: int

    # DCC document type designators and descriptions.
    _document_type_letters = {
        "C": "Contractual or procurement",
        "D": "Drawings",
        "E": "Engineering documents",
        "F": "Forms and Templates",
        "G": "Presentations (eg Graphics)",
        "L": "Letters and Memos",
        "M": "Management or Policy",
        "P": "Publications",
        "Q": "Quality Assurance documents",
        "S": "Serial numbers",
        "T": "Techical notes",
    }

    def __init__(self, first_id, numeric=None, version=None):
        # Copy constructor.
        if isinstance(first_id, DCCNumber):
            category = str(first_id.category)
            numeric = str(first_id.numeric)
            version = int(first_id.version)
        elif numeric is None:
            # Full number specified in the first argument. Check it's long enough.
            if len(first_id) < 2:
                raise ValueError("Invalid DCC number; should be of the form 'T0123456'")

            # Get rid of first "LIGO-" if present.
            if first_id.startswith("LIGO-"):
                first_id = first_id[len("LIGO-") :]

            try:
                # Find where the hyphen denoting the version is.
                hyphen_index = first_id.index("-")
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
                numeric = str(first_id[1:hyphen_index])

                # Version is last part, two places beyond start of hyphen.
                version = int(first_id[hyphen_index + 2 :])
            else:
                # Numeric is everything after first character.
                numeric = str(first_id[1:])

            # Category should be first.
            category = str(first_id[0])
        else:
            # Category is the first argument.
            category = str(first_id)

        # Check category is valid.
        if not DCCNumber.is_category_letter(category):
            raise InvalidDCCNumberException()

        # Check number is valid.
        if not DCCNumber.is_dcc_numeric(numeric):
            raise InvalidDCCNumberException()

        # Validate version if it was found.
        if version is not None:
            version = int(version)

            # Check version is valid.
            if not DCCNumber.is_dcc_version(version):
                raise InvalidDCCNumberException()

        self.category = category
        self.numeric = numeric
        self.version = version

    @classmethod
    def is_category_letter(cls, letter):
        """Checks if the specified category letter is valid.

        :param letter: category letter to check
        """

        # check if letter is in list of valid letters
        return letter in cls._document_type_letters

    @staticmethod
    def is_dcc_numeric(numeric):
        """Checks if the specified number is a valid DCC numeral.

        :param numeric: DCC numeral to check
        """

        # just check if the number is a positive integer
        return int(numeric) > 0

    def numbers_equal(self, other):
        """Check if the category and numeric parts of this number and the specified one
        match.

        :param other: other DCC number to check match for
        """

        # Compare the category and number.
        return other.category == self.category and other.numeric == self.numeric

    def string_repr(self, version=True):
        """String representation of the DCC number, with optional version number.

        :param version: whether to include version in string
        """
        version_string = self.version_suffix if version else ""
        return f"{self.category}{self.numeric}{version_string}"

    def has_version(self):
        """Checks if the DCC number has a version associated with it."""
        return self.version is not None

    @staticmethod
    def is_dcc_version(version):
        """Checks if the specified version number is valid.

        :param version: version to check
        """

        return int(version) >= 0

    @property
    def version_suffix(self):
        """The string version suffix for the version number."""

        # Version 0 should end "x0", otherwise "v1" etc.
        if not self.has_version():
            return ""
        elif self.version == 0:
            return "-x0"
        else:
            return f"-v{self.version}"

    def url_path(self, xml=True):
        """Returns the URL path that represents this DCC number.

        :param xml: whether to append the XML request string
        """

        xml_suffix = "/of=xml" if xml else ""

        # Return the URL with appropriate version suffix.
        return f"{self.category}{self.numeric}{self.version_suffix}{xml_suffix}"

    def __str__(self):
        return self.string_repr(version=True)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented

        # Compare the category, number and version.
        return self.numbers_equal(other) and other.version == self.version


@dataclass
class DCCDocID:
    """A DCC document ID."""

    docid: int
    version: int = None

    def __init__(self, docid, version=None):
        docid = int(docid)

        # Validate version if it was found.
        if version is not None:
            if not DCCNumber.is_dcc_version(version):
                raise InvalidDCCDocIDException()

            version = int(version)

        self.docid = int(docid)
        self.version = version

    def string_repr(self, version=True):
        """String representation of the document ID, with optional version number.

        :param version: whether to include version in string
        """
        version_string = ""
        if version and self.version is not None:
            version_string = f"-{self.version:d}"

        return f"{self.docid}{version_string}"

    def __str__(self):
        return self.string_repr(version=True)

    def __eq__(self, other):
        return self.docid == other.docid and self.version == other.version


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

    def fetch(self, file_=None, host=DEFAULT_HOST, idp=DEFAULT_IDP, force=False):
        """Fetch the file contents."""
        if not force and self.local_path is not None and self.local_path.exists():
            LOGGER.warning(
                f"{self} already fetched at {self.local_path}; use force to re-download"
            )
            return

        if file_ is None:
            file_ = NamedTemporaryFile("wb", delete=False, suffix=self.filename.suffix)

        # Get the file contents from the DCC.
        with DCCSession(host=host, idp=idp) as session, opened_file(
            file_, "wb"
        ) as fobj:
            for chunk in session.fetch_file(self):
                file_.write(chunk)

            self.local_path = Path(fobj.name)

    def open(self):
        """Open the file using the operating system."""
        if self.local_path is None:
            raise DataNotDownloadedException()

        click.launch(str(self.local_path))

    def write(self, path):
        """Write file to `path`."""
        if self.local_path is None:
            raise DataNotDownloadedException()

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
        """String representation of this journal reference."""

        journal = self.journal if self.journal else "Unknown journal"
        volume = self.volume if self.volume else "?"
        page = self.page if self.page else "?"
        url = f" ({self.url})" if self.url else ""

        return f"{journal} vol. {volume}, pg. {page}{url}"


@dataclass
class DCCRecord:
    """A DCC record."""

    dcc_number: DCCNumber
    docid: DCCDocID = None
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
    referenced_by: List[DCCDocID] = None
    related_to: List[DCCDocID] = None

    def __str__(self):
        return f"{self.dcc_number}: {self.title}"

    @classmethod
    def fetch(cls, dcc_number, host=DEFAULT_HOST, idp=DEFAULT_IDP):
        """Fetches and creates a new DCC record.

        Optionally downloads associated files.

        :param dcc_number: DCC number associated with the record to fetch
        """
        dcc_number = DCCNumber(dcc_number)

        # Get the document contents from the DCC.
        with DCCSession(host=host, idp=idp) as session:
            response = session.fetch_record_page(dcc_number)

        # Parse the document.
        parsed = DCCRecordParser(response.text)
        parsed_dcc_number = DCCNumber(*parsed.dcc_number_pieces)

        # Make sure the record matches the request.
        if not parsed_dcc_number.numbers_equal(dcc_number):
            raise DifferentDCCRecordException(
                f"The retrieved record, {parsed_dcc_number}, is different from the "
                f"requested one, {dcc_number}."
            )
        elif (
            dcc_number.version is not None
            and parsed.dcc_number.version != dcc_number.version
        ):
            # Correct document number, but incorrect version.
            raise DifferentDCCRecordException(
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

        return DCCRecord(
            dcc_number=parsed_dcc_number,
            docid=DCCDocID(parsed.docid),
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
            files=[DCCFile(*file_) for file_ in parsed.attached_files],
            referenced_by=[DCCDocID(*rel) for rel in parsed.referencing_ids],
            related_to=[DCCDocID(*rel) for rel in parsed.related_ids],
        )

    def fetch_files(self, force=False):
        for file_ in self.files:
            file_.fetch(force=force)

    @property
    def author_names(self):
        """Returns a list of author names associated with this record."""

        return [author.name for author in self.authors]

    @property
    def version_numbers(self):
        """Returns versions associated with this record."""

        versions = set(self.other_versions)
        versions.add(self.dcc_number.version)

        return versions

    @property
    def filenames(self):
        """Returns a list of filenames associated with this record."""

        return [str(file_) for file_ in self.files]

    @property
    def latest_version_number(self):
        """The latest version number for this record."""

        # find highest other version
        max_other_version = max(self.other_versions)

        # check if this is greater than the current version
        if max_other_version > self.dcc_number.version:
            return max_other_version

        return self.dcc_number.version

    def is_latest_version(self):
        return self.dcc_number.version is self.latest_version_number

    def refenced_by_titles(self):
        """Titles of documents referencing this one."""

        return [str(record) for record in self.referenced_by]

    def related_titles(self):
        """Titles of documents related to this one."""

        return [str(record) for record in self.related]


class InvalidDCCNumberException(Exception):
    """Exception for when a DCC number is invalid."""


class NoVersionSpecifiedException(Exception):
    """Exception for when a DCC number has not got a version specified."""


class InvalidDCCDocIDException(Exception):
    """Exception for when a document id is invalid."""


class DifferentDCCRecordException(Exception):
    """Exception for when a different DCC record is retrieved compared to the requested
    one."""


class DataNotDownloadedException(Exception):
    """Exception for when file data is not downloaded."""


class RecordCannotBeOverwrittenException(Exception):
    """Exception for when a record can't be overwritten due to a user option."""
