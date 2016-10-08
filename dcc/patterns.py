# -*- coding: utf-8 -*-

"""Pattern matching classes"""

import abc
import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup as bs
import pytz
import dcc.record

class DccPatterns(object):
    """Handles extraction of useful information from DCC pages."""

    # DCC category and number regular expression
    _dcc_number_regex = "([a-z])(\\d+)(-[vx](\\d+))?"

    # DCC record version regular expression
    # Version strings on the DCC are either -vX where X is an integer > 0, or -x0
    _dcc_record_version_regex = "[a-z]\\d+-[vx](\\d+)"

    # author ID url regular expression
    _author_url_id_regex = ".*?authorid=(\\d+)"

    # regex string match settings
    str_match_settings = re.IGNORECASE

    def __init__(self):
        """Instantiates a DccPatterns object, compiling some useful regular expressions"""

        # create logger
        self.logger = logging.getLogger("patterns")

        # regex matching DCC category and number in strings of the form "T0000000"
        self._regex_dcc_number = re.compile(self._dcc_number_regex, self.str_match_settings)

        # regex matching DCC category and number within a larger string
        self._regex_dcc_number_mixed = re.compile(".*?" + self._dcc_number_regex \
            + ".*?", self.str_match_settings)

        # regex matching DCC record version in strings of the form "T0000000-v5"
        self._regex_dcc_record_version = re.compile( \
            self._dcc_record_version_regex, self.str_match_settings)

        # regex matching DCC record version within a larger string
        self._regex_dcc_record_version_mixed = re.compile(".*?" \
            + self._dcc_record_version_regex + ".*?", self.str_match_settings)

        # regex matching author IDs
        self._regex_url_author_id = re.compile(self._author_url_id_regex)

    def get_dcc_number_from_string(self, string):
        """Extracts the DCC number from a string and returns a DccNumber object

        :param string: string to match DCC number in
        """

        # search for matches and pass them to another function to validate and create the object
        return DccPatterns._dcc_number_from_regex_search( \
            self._regex_dcc_number_mixed.search(string))

    def get_version_from_string(self, string):
        """Extracts the DCC record version from a string and returns it

        :param string: string to match DCC record version in
        """

        # search for matches and pass them to another function to validate and create the object
        return DccPatterns._version_from_regex_search( \
            self._regex_dcc_record_version_mixed.search(string))

    def get_author_id_from_url(self, url):
        """Extracts the author ID from an author URL

        :param url: URL to extract ID from
        """

        # search for id
        search = self._regex_url_author_id.search(url)

        # if the regex search is NoneType, no id was found
        if search is None:
            raise DccAuthorIdNotFoundException()

        # extract group
        group = search.groups()

        # first match is the ID
        return int(group[0])

    @staticmethod
    def _dcc_number_from_regex_search(regex_search):
        """Validates the matched values in a regular expression search for a DCC number in a string

        :param regex_search: search results object from regular expression
        """

        # if the regex search is NoneType, that means no valid values were found
        if regex_search is None:
            raise DccNumberNotFoundException()

        # extract group
        group = regex_search.groups()

        # first match is the category
        category_letter = str(group[0])

        # second match is the number
        dcc_numeric = int(group[1])

        # check if a version was matched
        if len(group) > 3:
            # version is 3rd item
            version = int(group[3])
        else:
            version = None

        # return a new DccNumber object representing the matched information
        return dcc.record.DccNumber(category_letter, dcc_numeric, version)

    @staticmethod
    def _version_from_regex_search(regex_search):
        """Validates the matched values in a regular expression search for a DCC record version in \
        a string

        :param regex_search: search results object from regular expression
        """

        # if the regex search is NoneType, that means no valid values were found
        if regex_search is None:
            raise DccNumberNotFoundException()

        # extract group
        group = regex_search.groups()

        # first match is the version
        version = int(group[0])

        return version

class DccPageParser(object):
    """Represents a parser for DCC pages"""

    # abstract method
    __metaclass__ = abc.ABCMeta

    def validate(self):
        """Validates the page content to make sure it is a proper record"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # check if we have the login page, specified by the presence of an h3 with specific text
        if navigator.find("h3", text="Accessing private documents"):
            raise NotLoggedInException()

        # check if we have the default page (DCC redirects here for all unrecognised requests)
        if navigator.find("strong", text="Search for Documents by"):
            raise UnrecognisedDccRecordException()

        # check if we have the error page
        if navigator.find("dt", class_="Error"):
            # we have an error, but what is its message?
            if navigator.find("dd", text=re.compile("User .*? is not authorized to view this document.")):
                # unauthorised to view
                raise UnauthorisedAccessException()
            else:
                # unknown error
                raise UnknownDccErrorException()

class DccRecordParser(DccPageParser):
    """Represents a parser for DCC HTML documents"""

    def __init__(self, content):
        """Instantiates a record parser with the provided page content

        :param content: DCC record page HTML
        """

        # create logger
        self.logger = logging.getLogger("record-parser")

        # create patterns object
        self.dcc_patterns = DccPatterns()

        # set page content
        self.content = content

    def _get_content_navigator(self):
        """Gets a navigator object for the page content"""

        # create and return a BeautifulSoup object
        return bs(self.content, "html.parser")

    def extract_dcc_number(self):
        """Extracts the DCC number"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # find document number element
        doc_num_h = navigator.find("h1", id="title")

        # make sure it was found
        if doc_num_h is None:
            raise DccRecordTitleNotFoundException()

        # get and return DCC number
        return self.dcc_patterns.get_dcc_number_from_string(doc_num_h.string)

    def extract_title(self):
        """Extracts the title from the page content"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # find div holding title
        doc_title_div = navigator.find("div", id="DocTitle")

        # make sure it was found
        if doc_title_div is None:
            raise DccRecordTitleNotFoundException()

        # the document title is the entire string contained within h1 within this div
        title = str(doc_title_div.find("h1").string)

        return title

    def extract_other_version_numbers(self):
        """Extract a list of other version numbers from the page content"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # get div containing other versions
        versions_div = navigator.find("div", id="OtherVersions")

        # check it was found
        if versions_div is None:
            raise DccRecordTitleNotFoundException()

        # find all DCC strings in the list of anchor elements
        return [self.dcc_patterns.get_version_from_string(str(tag["title"])) \
            for tag in versions_div.find_all("a")]

    def extract_attached_files(self):
        """Extract a list of attached files from the page content"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # get files lists
        files_classes = navigator.find_all("dd", class_="FileList")

        # empty files list
        files = []

        # loop over found classes, searching for URLs and creating DccFile objects in the list
        for files_class in files_classes:
            files.extend([dcc.record.DccFile(str(url_tag.string), str(url_tag["title"]), \
                str(url_tag["href"])) for url_tag in files_class.find_all("a")])

        # return list of DccFile objects
        return files

    def extract_revision_dates(self):
        """Extracts the revision dates from the content, converted to a Python dates"""

        # get the creation, contents and metadata revision date texts
        creation_date_string = self._extract_revision_date_string("Document Created:")
        contents_rev_date_string = self._extract_revision_date_string("Contents Revised:")
        metadata_rev_date_string = self._extract_revision_date_string("Metadata Revised:")

        # parse strings as dates, which are DCC times
        creation_date = DccRecordParser._parse_dcc_date_string(creation_date_string)
        contents_rev_date = DccRecordParser._parse_dcc_date_string(contents_rev_date_string)
        metadata_rev_date = DccRecordParser._parse_dcc_date_string(metadata_rev_date_string)

        # return tuple
        return (creation_date, contents_rev_date, metadata_rev_date)

    def extract_referencing_records(self):
        """Extracts the referencing records from the page"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # empty list of references
        references = []

        # get the reference div
        ref_div = navigator.find("div", id="XReffedBy")

        # if there is no reference div, return
        if ref_div is None:
            return references

        # extract reference links
        reference_links = ref_div.find_all("a")

        # if there are no references, return
        if reference_links is None:
            return references

        # loop over references
        for reference_link in reference_links:
            # create new DCC record for the reference
            record = dcc.record.DccRecord(dcc.record.DccNumber(str(reference_link['title'])))

            # set its title
            record.title = str(reference_link.text)

            # add to list
            references.append(record)

        # return list of references
        return references

    def extract_related_records(self):
        """Extracts the related records from the page"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # empty list of related documents
        related = []

        # get the related div
        related_div = navigator.find("div", id="XRefs")

        # if there is no related div, return
        if related_div is None:
            return related

        # extract related links
        related_links = related_div.find_all("a")

        # if there are no related links, return
        if related_links is None:
            return related

        # loop over related links
        for related_link in related_links:
            # create new DCC record for the related document
            record = dcc.record.DccRecord(dcc.record.DccNumber(str(related_link['title'])))

            # set its title
            record.title = str(related_link.text)

            # add to list
            related.append(record)

        # return list of related documents
        return related

    def extract_authors(self):
        """Extracts the authors from the page"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # empty list of authors
        authors = []

        # get the author div
        author_div = navigator.find("div", id="Authors")

        # if there is no author div, return
        if author_div is None:
            return authors

        # extract author links
        author_links = author_div.find_all("a")

        # if there are no author links, return
        if author_links is None:
            return authors

        # loop over author links
        for author_link in author_links:
            # skip email links
            if author_link['href'].startswith('mailto'):
                continue

            # get name, with strip() to get rid of whitespace
            author_name = author_link.text.strip()

            # get id
            author_id = self.dcc_patterns.get_author_id_from_url( \
            author_link['href'])

            # create author object
            author = dcc.record.DccAuthor(author_name, author_id)

            # add to list
            authors.append(author)

        return authors

    @staticmethod
    def _parse_dcc_date_string(date_string):
        """Returns a DateTime object from the specified date string, assuming the Pacific timezone

        :param date_string: date string to parse
        """

        # create Pacific timezone
        pacific = pytz.timezone("US/Pacific")

        # parse date string localised to Pacific Time
        return pacific.localize(datetime.strptime(date_string, "%d %b %Y, %H:%M"))

    def _extract_revision_date_string(self, previous_element_contents):
        """Extracts a revision info date string as specified by the previous element text

        This can be used to find the creation, contents and metadata revision times from the DCC
        document by matching the previous element's text, e.g. "Document Created:".

        :param previous_element_contents: exact textual contents of the previous element to the \
        one to find
        """

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # get div containing revision dates
        revisions_div = navigator.find("div", id="RevisionInfo")

        # check it was found
        if revisions_div is None:
            raise DccRecordRevisionsNotFoundException()

        # find date title
        date_dt = DccRecordParser._find_child_by_text(revisions_div, previous_element_contents)

        # check it was found
        if date_dt is None:
            raise DccRecordRevisionsNotFoundException()

        # get next dd element, which should contain the date
        date_dd = date_dt.find_next("dd")

        # check it was found
        if date_dd is None:
            raise DccRecordRevisionsNotFoundException()

        # parse the date text
        return str(date_dd.text)

    @staticmethod
    def _find_child_by_text(base_element, text, tag=None, class_=None):
        """Returns the child after the element identified by the specified filter criteria

        :param base_element: base element to search children of
        :param text: exact text contents to search for
        :param tag: tag type to search for
        :param class_: class to search for
        """

        # validate text
        text = str(text)

        # arguments for find
        args = []
        kwargs = {}

        # add tag search as first argument, if present
        if tag is not None:
            args.append(tag)

        # add class search if present
        if class_ is not None:
            kwargs["class_"] = class_

        # iterate over children
        for element in base_element.find_all(*args, **kwargs):
            # check if the text matches
            if element.text == text:
                return element

        # no element found
        return None

class DccAuthorPageParser(DccPageParser):
    """Represents a parser for DCC author pages"""

    def __init__(self, content):
        """Instantiates an author page parser with the provided page content

        :param content: DCC author page HTML
        """

        # create logger
        self.logger = logging.getLogger("author-parser")

        # create patterns object
        self.dcc_patterns = DccPatterns()

        # set page content
        self.content = content

    def _get_content_navigator(self):
        """Gets a navigator object for the page content"""

        # create and return a BeautifulSoup object
        return bs(self.content, "html.parser")

class DccNumberNotFoundException(Exception):
    """Exception for when a DCC number is not found"""
    pass

class DccAuthorIdNotFoundException(Exception):
    """Exception for when a DCC author ID is not found"""
    pass

class DccRecordTitleNotFoundException(Exception):
    """Exception for when a DCC record title is not found in the page content"""
    pass

class DccRecordRevisionsNotFoundException(Exception):
    """Exception for when DCC record revisions are not found in the page content"""
    pass

class NotLoggedInException(Exception):
    """Exception for when the user is not logged in"""

    # error message given to user
    message = "You are not logged in to the DCC, or the specified cookie string is invalid (see \
the README for more information)"

    def __init__(self, *args, **kwargs):
        """Constructs a not logged in exception"""

        # call parent constructor with the error message
        super(NotLoggedInException, self).__init__(self.message, *args, **kwargs)

class UnrecognisedDccRecordException(Exception):
    """Exception for when a page is not recognised by the DCC server"""
    pass

class UnauthorisedAccessException(Exception):
    """Exception for when a document is not available to the user to be viewed"""
    pass

class UnknownDccErrorException(Exception):
    """Exception for when an unknown error is reported by the DCC"""
    pass
