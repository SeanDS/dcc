# -*- coding: utf-8 -*-

"""Record classes"""

import sys
import os
import logging
import subprocess
import tempfile

class DccAuthor(object):
    """Represents a DCC author"""

    # author name
    name = None

    def __init__(self, name):
        """Instantiates a DCC author

        :param name: name of the author
        """

        # set name
        self.name = str(name)

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

    # category
    category = None

    # numeric part
    numeric = None

    # version of the DCC record
    version = None

    def __init__(self, first_id, numeric=None, version=None):
        """Instantiates a DccNumber object

        You must either provide a string containing the DCC number, or the
        separate category and numeric parts, with optional version, e.g.
            __init__("T1234567")
            __init__("T", 1234567) # equivalent to T1234567
            __init__("T", 1234567, 4) # equivalent to T1234567-v4

        :param first_id: category character, or the full DCC number
        :param numeric: numeric designator of DCC document
        :param version: version number of DCC document
        """

        # create logger
        self.logger = logging.getLogger("number")

        if numeric is None:
            # full number specified, so check it's long enough
            if len(first_id) < 2:
                raise ValueError("Invalid DCC number; should be of the form \"T1234567\"")

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
                numeric = int(first_id[1:hyphen_index])

                # version is last part, two places beyond start of hyphen
                version = int(first_id[hyphen_index+2:])
            else:
                # numeric is everything after first character
                numeric = int(first_id[1:])

            # category should be first
            category = str(first_id[0])
        else:
            # category is the first argument
            category = str(first_id)

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

    def __str__(self):
        """String representation of the DCC number"""

        return "{0}{1}{2}".format(self.category, self.numeric, self.get_version_suffix())

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
        if self.version is None:
            return "-v?"
        elif self.version is 0:
            return "-x0"
        else:
            return "-v{0}".format(self.version)

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

    # record title
    title = None

    # authors
    authors = None

    # other version numbers associated with this record
    other_version_numbers = []

    # revision dates
    creation_date = None
    contents_revision_date = None
    metadata_revision_date = None

    # files associated with this record
    files = []

    # referencing documents
    referenced_by = []

    # related documents
    related = []

    def __init__(self, dcc_number):
        """Instantiates a DCC record

        :param dcc_number: DCC number object representing the record
        """

        # create logger
        self.logger = logging.getLogger("record")

        self.dcc_number = dcc_number

    def __str__(self):
        """String representation of the DCC record"""

        return "{0}: {1}".format(self.dcc_number, self.title)

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

        return [str(dcc_file) for dcc_file in self.files]

    def add_version_number(self, version_number):
        """Adds the specified other version number to the record

        :param version_number: version number to add
        """

        # validate
        version_number = int(version_number)

        self.logger.debug("Adding other version number %d", version_number)

        # add to version list
        self.other_version_numbers.append(version_number)

    def add_file(self, dcc_file):
        """Adds the specified file to the record

        :param dcc_file: DCC file to add
        """

        self.logger.debug("Adding file %s", dcc_file)

        # add to file list
        self.files.append(dcc_file)

    def get_lastest_version_number(self):
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

        return [str(record) for record in self.referenced_by]

    def get_related_titles(self):
        """Returns a list of titles of documents related to this one"""

        return [str(record) for record in self.related]

class DccFile(object):
    """Represents a file attached to a DCC document"""

    # file data
    data = None

    # local path
    local_path = None

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

    def __str__(self):
        """String representation of the DCC record"""

        return "{0} ({1})".format(self.title, self.filename)

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

        self.logger.info("Opening file...")

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

        # get a temporary file, with a guaranteed name and not deleted immediately
        tmp_file = tempfile.NamedTemporaryFile(delete=False)

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

class DataNotDownloadedException(Exception):
    """Exception for when file data is not downloaded"""
    pass