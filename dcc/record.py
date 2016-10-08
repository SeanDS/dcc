# -*- coding: utf-8 -*-

"""Record classes"""

from __future__ import unicode_literals

import sys
import os
import logging
import subprocess
import tempfile
import dcc.comms
import dcc.patterns

class DccArchive(object):
    """Represents a collection of DCC documents"""

    def __init__(self, fetcher='http', cookies='', progress_hook=None):
        """Instantiates a DCC archive

        :param fetcher: type of fetcher to use, or fetcher object
        :param cookies: cookies to pass to fetcher, if necessary
        :param progress_hook: callable to send download progress to
        """

        # create logger
        self.logger = logging.getLogger("archive")

        # parse the stated fetch method
        if isinstance(fetcher, dcc.comms.Fetcher):
            # a fetcher was provided already
            self.fetcher = fetcher
        else:
            # validate fetcher and cookies as strings
            fetcher = unicode(fetcher)
            cookies = unicode(cookies)

            if fetcher == 'http':
                # create an HTTP fetcher
                self.fetcher = dcc.comms.HttpFetcher(cookies)
            else:
                # fetcher not recognised
                raise FetcherNotRecognisedException()

        # set the progress hook
        self.fetcher.progress_hook = progress_hook

        # create empty archive dict
        self.records = {}

    def __str__(self):
        """String representation of the archive"""

        return "Archive containing {0} record(s)".format(len(self.records))

    def __repr__(self):
        """Print representation of the archive"""

        return unicode(self)

    def fetch_record(self, *args, **kwargs):
        """Fetches a DCC record and adds it to the archive

        :param download_files: whether to download the files attached to the record
        :param overwrite: whether to overwrite an existing identical record
        """

        # get download_files parameter (a bit hacky due to Python 2's argument handling behaviour)
        download_files = bool(kwargs.get('download_files', False))

        # get overwrite parameter
        overwrite = bool(kwargs.get('overwrite', False))

        # remove download_files from kwargs
        if kwargs.has_key('download_files'):
            del kwargs['download_files']

        # remove overwrite from kwargs
        if kwargs.has_key('overwrite'):
            del kwargs['overwrite']

        # get DCC number from input(s)
        if isinstance(args[0], DccNumber):
            # DCC number provided
            dcc_number = args[0]
        else:
            # DCC number to be created from inputs
            dcc_number = DccNumber(*args, **kwargs)

        # create record
        record = DccRecord._fetch(self.fetcher, dcc_number)

        # download the files associated with the record, if requested
        if download_files:
            self.download_record_file_data(record)

        # add record to archive
        self.add_record(record, overwrite=overwrite)

        # return the record
        return record

    def add_record(self, record, overwrite=False):
        """Adds the specified record to the archive

        :param record: record to add
        :param overwrite: whether to overwrite an existing record
        """

        # get the DCC number string
        dcc_number_str = dcc.record.DccArchive.get_dcc_number_str(record.dcc_number)

        # check if record already exists
        if dcc_number_str in self.records.keys():
            # check if the user wants it overwritten
            if not overwrite:
                # user doesn't want overwriting, so raise an exception
                raise RecordCannotBeOverwrittenException()

            self.logger.info("Overwriting existing entry %s", dcc_number_str)

        # set the record
        self.records[dcc_number_str] = record

        self.logger.info("Entry %s written to archive", dcc_number_str)

    def has_record(self, dcc_number):
        """Works out if the specified DCC number exists in the archive

        The DCC number specified can either be a string or a DccNumber object, but it must contain
        a version number. For non-versioned searches, use has_document.

        :param dcc_number: DCC number to check, either a string or a DccNumber
        """

        # if the number is not a DccNumber, parse it as one
        if not isinstance(dcc_number, dcc.record.DccNumber):
            dcc_number = dcc.record.DccNumber(unicode(dcc_number))

        # make sure a version is present
        if not dcc_number.has_version():
            raise NoDccRecordVersionSpecifiedException()

        # check if the DCC number string is in the record dict keys
        return dcc.record.DccArchive.get_dcc_number_str(dcc_number) in self.records.keys()

    def has_document(self, dcc_number):
        """Checks if the archive contains any version of the specified DCC number

        This is much less efficient than has_record.

        :param dcc_number: DCC number to check
        """

        # if the number is not a DccNumber, parse it as one
        if not isinstance(dcc_number, dcc.record.DccNumber):
            dcc_number = dcc.record.DccNumber(unicode(dcc_number))

        # if a version is present, tell the user it is being ignored
        if dcc_number.has_version():
            self.logger.info("Ignoring version number in search for %s", dcc_number)

        # get the DCC number string without version suffix
        dcc_number_str = dcc_number.string_repr(version=False)

        # search for records beginning with the no-version number
        for this_dcc_str, record in self.records.items():
            # parse a DCC number from the key
            this_dcc_number = dcc.record.DccNumber(this_dcc_str)

            # check if the strings match
            if this_dcc_number.string_repr(version=False) == dcc_number_str:
                # found a match
                return True

        return False

    def list_records(self):
        """Lists the records contained within the archive"""

        return [unicode(record) for record in self.records.values()]

    def download_record_file_data(self, record):
        """Downloads the file data attached to the specified record

        :param record: DCC record to download files for
        """

        # count files
        total_count = len(record.files)

        # current file count
        current_count = 1

        # loop over files in this record
        for dcc_file in record.files:
            self.logger.info("(%d/%d) Fetching %s", current_count, total_count, dcc_file)

            # fetch file contents
            self.download_file_data(dcc_file)

            # increment counter
            current_count += 1

    def download_file_data(self, dcc_file):
        """Fetches the files attached to the specified record

        :param dcc_file: file to download data for
        """

        # download the file
        dcc_file._download(self.fetcher)

    def get_author_dcc_numbers(self, author):
        """Fetches the DCC numbers associated with the author

        Note that this is limited by the DCC's limit on returned records
        (default 500).

        :param author: author to fetch numbers for
        """

        # return the author's numbers
        return author._get_dcc_numbers(self.fetcher)

    @staticmethod
    def get_dcc_number_str(dcc_number, version=True):
        """Creates a string representing the specified DCC number, optionally with version

        :param version: whether to include version
        """

        # use the DCC number's string representation method
        return dcc_number.string_repr(version=version)

class DccAuthor(object):
    """Represents a DCC author"""

    def __init__(self, name, uid):
        """Instantiates a DCC author

        :param name: name of the author
        :param uid: DCC ID number for the author
        """

        # set name
        self.name = unicode(name)

        # set id
        self.uid = int(uid)

    def __str__(self):
        """String representation of this author"""

        return "{0} (id {1})".format(self.name, self.uid)

    def __repr__(self):
        """Representation of this author"""

        return self.__str__()

    def _get_dcc_numbers(self, fetcher):
        """Fetches a list of DCC numbers from this author

        Note that this may not be complete due to the DCC's limit on the number
        of documents displayed on the author's page (default 500).

        :param fetcher: fetcher object to use
        """

        # download author page
        author_page = fetcher.fetch_author_page(self)

        # parse the page
        parser = dcc.patterns.DccAuthorPageParser(author_page)

        # check that we have a valid author page
        parser.validate()

        # get the list of DCC numbers
        return parser.extract_dcc_numbers()

class DccNumber(object):
    """Represents a DCC number, including category and numeric identifier"""

    # DCC document type designators and descriptions
    document_type_letters = {
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
        "T": "Techical notes"
    }

    def __init__(self, first_id, numeric=None, version=None):
        """Instantiates a DccNumber object

        You must either provide a string containing the DCC number, or the
        separate category and numeric parts, with optional version, e.g.
            __init__("T1234567")
            __init__("T", "0123456") # equivalent to T0123456
            __init__("T", "0123456", 4) # equivalent to T0123456-v4

        :param first_id: category character, or the full DCC number
        :param numeric: numeric designator of DCC document
        :param version: version number of DCC document
        """

        # create logger
        self.logger = logging.getLogger("number")

        if numeric is None:
            # full number specified, so check it's long enough
            if len(first_id) < 2:
                raise ValueError("Invalid DCC number; should be of the form \"T0123456\"")

            # get rid of first "LIGO-" if present
            if first_id.startswith('LIGO-'):
                # chop off first 5 characters
                first_id = first_id[5:]

            try:
                # find where the hyphen denoting version is
                hyphen_index = first_id.index('-')
            except ValueError:
                # couldn't find it
                hyphen_index = None

            if hyphen_index is not None:
                # check if the version was specified, and if so, warn the user
                if version is not None:
                    self.logger.warning("Version argument ignored as it was specified in the DCC \
                        string")

                # numeric part is between second character and index
                numeric = unicode(first_id[1:hyphen_index])

                # version is last part, two places beyond start of hyphen
                version = int(first_id[hyphen_index+2:])
            else:
                # numeric is everything after first character
                numeric = unicode(first_id[1:])

            # category should be first
            category = unicode(first_id[0])
        else:
            # category is the first argument
            category = unicode(first_id)

        # check category is valid
        if not DccNumber.is_category_letter(category):
            raise InvalidDccNumberException()

        # check number is valid
        if not DccNumber.is_dcc_numeric(numeric):
            raise InvalidDccNumberException()

        # validate version if it was found
        if version is not None:
            # check version is valid
            if not DccNumber.is_dcc_version(version):
                raise InvalidDccNumberException()

        # set everything
        self.category = category
        self.numeric = numeric
        self.version = version

    @classmethod
    def is_category_letter(cls, letter):
        """Checks if the specified category letter is valid

        :param letter: category letter to check
        """

        # check if letter is in list of valid letters
        return letter in cls.document_type_letters.keys()

    @staticmethod
    def is_dcc_numeric(numeric):
        """Checks if the specified number is a valid DCC numeral

        :param numeric: DCC numeral to check
        """

        # just check if the number is a positive integer
        return int(numeric) > 0

    @staticmethod
    def is_dcc_version(version):
        """Checks if the specified version number is valid

        :param version: version to check
        """

        return int(version) >= 0

    def numbers_equal(self, other_dcc_number):
        """Checks if the category and numeric parts of this number and the specified one match

        :param other_dcc_number: other DCC number to check match for
        """

        # compare the category and number
        return (other_dcc_number.category == self.category) and \
            (other_dcc_number.numeric == self.numeric)

    def string_repr(self, version=True):
        """String representation of the DCC number, with optional version number

        :param version: whether to include version in string
        """

        # empty version string
        version_string = ""

        # get version string if requested
        if version:
            version_string = self.get_version_suffix()

        return "{0}{1}{2}".format(self.category, self.numeric, version_string)

    def __str__(self):
        """String representation of the DCC number"""

        return self.string_repr(version=True)

    def __repr__(self):
        """Representation of the DCC number"""

        return self.__str__()

    def __eq__(self, other_dcc_number):
        """Checks if the specified DCC number is equal to this one

        :param other_dcc_number: other DCC number to compare
        """

        # compare the category, number and version
        return self.numbers_equal(other_dcc_number) and (other_dcc_number.version == self.version)

    def __ne__(self, other_dcc_number):
        """Checks if the specified DCC number is not equal to this one

        :param other_dcc_number: other DCC number to compare
        """

        return not self.__eq__(other_dcc_number)

    def get_version_suffix(self):
        """Returns the DCC URL suffix for the version number"""

        # version 0 should end "x0", otherwise "v1" etc.
        if not self.has_version():
            return "-v?"
        elif self.version is 0:
            return "-x0"
        else:
            return "-v{0}".format(self.version)

    def has_version(self):
        """Checks if the DCC number has a version associated with it"""

        return self.version is not None

    def get_url_path(self):
        """Returns the URL path that represents this DCC number"""

        # get version suffix, if it is known
        if self.version is not None:
            version_suffix = self.get_version_suffix()
        else:
            # make version empty
            version_suffix = ""

        # return the URL with appropriate version suffix
        return "{0}{1}{2}".format(self.category, self.numeric, version_suffix)

class DccRecord(object):
    """Represents a DCC record"""

    def __init__(self, dcc_number):
        """Instantiates a DCC record

        :param dcc_number: DCC number object representing the record
        """

        # create logger
        self.logger = logging.getLogger("record")

        # set number
        self.dcc_number = dcc_number

        # set defaults
        self.other_version_numbers = []
        self.files = []
        self.referenced_by = []
        self.related = []

    def __str__(self):
        """String representation of this DCC record"""

        return "{0}: {1}".format(self.dcc_number, self.title)

    def __repr__(self):
        """Representation of this DCC record"""

        return self.__str__()

    @classmethod
    def _fetch(cls, fetcher, dcc_number):
        """Fetches and creates a new DCC record

        Optionally downloads associated files.

        :param fetcher: fetcher to use to get the page content
        :param dcc_number: DCC number associated with the record to fetch
        """

        # create logger
        logger = logging.getLogger("record")

        # get the page contents
        contents = fetcher.fetch_record_page(dcc_number)

        # parse new DCC record
        parser = dcc.patterns.DccRecordParser(contents)

        # check that we have a valid record
        parser.validate()

        # get DCC number
        this_dcc_number = parser.extract_dcc_number()

        # make sure its number matches the request
        if this_dcc_number.numbers_equal(dcc_number):
            # check if the version matches, if it was specified
            if dcc_number.version is not None:
                if this_dcc_number.version != dcc_number.version:
                    # correct document number, but incorrect version
                    raise DifferentDccRecordException("The retrieved record has the correct \
number but not the correct version")
        else:
            # incorrect document number
            raise DifferentDccRecordException("The retrieved record number ({0}) is different from the \
requested one ({1})".format(this_dcc_number, dcc_number))

        # create record with DCC number
        record = DccRecord(this_dcc_number)

        # set its title
        record.title = parser.extract_title()

        # set authors
        record.authors = parser.extract_authors()

        # get other version numbers
        record.other_version_numbers = parser.extract_other_version_numbers()
        logger.info("Found %d other version number(s)", len(record.other_version_numbers))

        # get the revision dates
        (creation_date, contents_rev_date, metadata_rev_date) = \
        parser.extract_revision_dates()

        # set them individually
        record.creation_date = creation_date
        record.contents_revision_date = contents_rev_date
        record.metadata_revision_date = metadata_rev_date

        # get attached files
        files = parser.extract_attached_files()

        # set the files
        map(record.add_file, files)
        logger.info("Found %d attached file(s)", len(files))

        # get and set the referencing records
        record.referenced_by = parser.extract_referencing_records()

        # get and set the related records
        record.related = parser.extract_related_records()

        # return the new record
        return record

    @property
    def author_names(self):
        """Returns a list of author names associated with this record"""

        return [author.name for author in self.authors]

    @property
    def versions(self):
        """Returns a list of versions associated with this record"""

        versions_list = self.other_version_numbers
        versions_list.append(self.dcc_number.version)

        return versions_list

    @property
    def filenames(self):
        """Returns a list of filenames associated with this record"""

        return [unicode(dcc_file) for dcc_file in self.files]

    def add_file(self, dcc_file):
        """Adds the specified file to the record

        :param dcc_file: DCC file to add
        """

        self.logger.debug("Adding file %s", dcc_file)

        # add to file list
        self.files.append(dcc_file)

    @property
    def latest_version(self):
        """Returns the latest version number for this record"""

        # find highest other version
        max_other_version = max(self.other_version_numbers)

        # check if this is greater than the current version
        if max_other_version > self.dcc_number.version:
            return max_other_version
        else:
            return self.dcc_number.version

    def get_refenced_by_titles(self):
        """Returns a list of titles of documents referencing this one"""

        return [unicode(record) for record in self.referenced_by]

    def get_related_titles(self):
        """Returns a list of titles of documents related to this one"""

        return [unicode(record) for record in self.related]

class DccFile(object):
    """Represents a file attached to a DCC document"""

    def __init__(self, title, filename, url):
        """Instantiates a DCC file object

        :param title: file title
        :param filename: filename
        :param url: file URL string
        """

        # create logger
        self.logger = logging.getLogger("file")

        self.title = title
        self.filename = filename
        self.url = url

        # defaults
        self.data = None
        self.local_path = None

    def __str__(self):
        """String representation of this DCC file"""

        return "{0} ({1})".format(self.title, self.filename)

    def __repr__(self):
        """Representation of this DCC file"""

        return self.__str__()

    def _download(self, fetcher):
        """Downloads the file using the specified fetcher

        :param fetcher: fetcher to use to get data
        """

        self.logger.info("Downloading and attaching %s", self)

        # download and attach data to file
        self.set_data(fetcher.fetch_file_data(self))

    def set_data(self, data):
        """Sets the data associated with this file

        :param data: data to set
        """

        # set the data
        self.data = data

    def open_file(self):
        """Opens the file using the operating system"""

        # check if the data is available
        if self.data is None:
            raise DataNotDownloadedException()

        # check if the file location exists
        if not self.has_local_path():
            self.create_temp_path()

        self.logger.info("Opening %s...", self.local_path)

        # check if Linux
        if sys.platform.startswith('linux'):
            # open with X.ORG
            subprocess.call(["xdg-open", self.local_path])
        else:
            # open with Python (this may not work on non-Windows)
            os.startfile(self.local_path)

    def has_local_path(self):
        """Checks if the file has a local path"""

        return self.local_path is not None

    def create_temp_path(self):
        """Creates and sets a temporary location for the file"""

        self.logger.info("Setting temporary path for %s", self)

        # get the file's suffix, if there is one
        dot_idx = self.filename.find('.')

        # check if the dot was found
        if dot_idx >= 0:
            # add the extension
            suffix = self.filename[dot_idx:]
        else:
            suffix = ""

        # get a temporary file, with a guaranteed name and not deleted immediately
        # suffix is required to allow intelligent opening of files in external apps
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

        self.logger.info("Writing data to temporary file")

        # write data to file
        tmp_file.write(self.data)

        # close file
        tmp_file.close()

        # set the (string) path
        self.local_path = tmp_file.name

class InvalidDccNumberException(Exception):
    """Exception for when a DCC number is invalid"""
    pass

class DifferentDccRecordException(Exception):
    """Exception for when a different DCC record is retrieved compared to the requested one"""
    pass

class DataNotDownloadedException(Exception):
    """Exception for when file data is not downloaded"""
    pass

class FetcherNotRecognisedException(Exception):
    """Exception for when the specified fetcher is not recognised"""
    pass

class RecordCannotBeOverwrittenException(Exception):
    """Exception for when a record can't be overwritten due to a user option"""
    pass

class NoDccRecordVersionSpecifiedException(Exception):
    """Exception for when no version is specified for a DCC record when required"""
    pass
