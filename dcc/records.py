"""Record objects."""

import logging
from typing import List
from pathlib import Path
import shutil
from dataclasses import dataclass, field, asdict
from itertools import takewhile
import datetime
import click
import toml
from .sessions import DCCSession
from .parsers import DCCRecordParser
from .util import opened_file
from .env import DEFAULT_HOST, DEFAULT_IDP
from .exceptions import NoVersionError

LOGGER = logging.getLogger(__name__)


def _default_session():
    return DCCSession(DEFAULT_HOST, DEFAULT_IDP)


class DCCArchive:
    """A collection of DCC documents."""

    def fetch_record(self, dcc_number, fetch_files=False, session=None):
        """Fetches a DCC record and adds it to the archive.

        :param overwrite: whether to force a new download even if the record is in the cache
        :param fetch_files: whether to download the files attached to the record
        """
        dcc_number = DCCNumber(dcc_number)

        # Fetch record.
        record = DCCRecord.fetch(dcc_number, session=session)

        if fetch_files:
            record.fetch_files(session=session)

        return record

    def load_record(self, dcc_number, session=None):
        return DCCRecord.load(session=session)


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

    :param category: category character, or the full DCC number
    :param numeric: numeric designator of DCC document
    :param version: version number of DCC document
    """

    category: str
    numeric: str
    version: int = None

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

    def url_path(self, xml=False):
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
        """Fetch the file contents."""
        if session is None:
            with _default_session() as session:
                return self.fetch_file_contents(session=session)

        self.local_path = session.file_archive_path(record, self)

        if not session.overwrite and self.local_path.exists():
            # The file is available in the local archive.
            LOGGER.info(f"{self} is already present in the local archive")
        else:
            # Fetch the remote file.
            LOGGER.info(f"Fetching {self} from DCC")

            if self.local_path.exists():
                LOGGER.info(f"Overwriting {self.local_path}")

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
        """Write file to `path`."""
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
        """Fetches and creates a new DCC record.

        Optionally downloads associated files.

        :param dcc_number: DCC number associated with the record to fetch
        """
        if session is None:
            with _default_session() as session:
                return cls.fetch(dcc_number, session=session)

        dcc_number = DCCNumber(dcc_number)

        # Only attempt to retrieve fully qualified records from archive.
        try:
            cache_dir = session.record_archive_dir(dcc_number)
        except NoVersionError:
            LOGGER.info(
                f"No version in specified code ({dcc_number}); cannot use local archive"
            )
            cache_dir = None
        except Exception:
            cache_dir = None

        if cache_dir is not None and not session.overwrite and cache_dir.exists():
            # Retrieve the cached record.
            LOGGER.info(f"Loading {dcc_number} from the local archive")

            try:
                record = cls.read(cache_dir)
            except FileNotFoundError as err:
                raise Exception(f"{err} (document in archive corrupt?)")
        else:
            # Fetch the remote record.
            LOGGER.info(f"Fetching {dcc_number} from DCC")
            record = cls._fetch_remote(dcc_number, session)

            # Archive the record.
            archive_dir = session.record_archive_dir(record.dcc_number)
            archive_dir.mkdir(parents=True, exist_ok=True)
            meta_file = cls._meta_file(archive_dir)
            if session.overwrite or not meta_file.exists():
                if meta_file.exists():
                    LOGGER.info(f"Overwriting {meta_file}")

                LOGGER.info(f"Archiving {record} metadata to {meta_file}")
                record.write(meta_file)
            else:
                # Only reached if the user specified a record number without a version,
                # but the version retrieved from the DCC already existed in the local
                # archive.
                LOGGER.info(
                    f"Refusing to overwrite existing file at {meta_file}; set "
                    f"session overwrite flag to force"
                )

        return record

    @classmethod
    def _fetch_remote(cls, dcc_number, session):
        # Get the document contents from the DCC.
        response = session.fetch_record_page(dcc_number)

        # Parse the document.
        parsed = DCCRecordParser(response.text)
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
        for file_ in self.files:
            file_.fetch_file_contents(record=self, session=session)

    def write(self, path):
        """Store the record on the file system."""
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
        """Read the record from the file system."""
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
            item["referenced_by"] = [DCCNumber(ref) for ref in item["referenced_by"]]
        if "related_ids" in item:
            item["related_ids"] = [DCCNumber(ref) for ref in item["related_ids"]]

        return DCCRecord(**item)

    @staticmethod
    def _meta_file(target_dir):
        return target_dir / "meta.toml"

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
