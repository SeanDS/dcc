# -*- coding: utf-8 -*-

"""Pattern matching classes"""


import abc
import logging
import re
from datetime import datetime
import xml.etree.ElementTree as ET
import pytz
from bs4 import BeautifulSoup as bs
import dcc.record


class DccRecordParser(object):
    """Represents a parser for DCC XML documents"""

    def __init__(self, content):
        """Instantiates a record parser with the provided page content

        :param content: DCC record page XML

        """
        self.logger = logging.getLogger("record-parser")
        self.content = content

    def validate(self):
        try:
            self.root = ET.fromstring(self.content)
        except ET.ParseError:
            # This is not an XML document
            # Do we have an error page instead? Use the HTML parser.

            # get an HTML navigator object for the record
            navigator = bs(self.content, "html.parser")

            # check if we have the login page, specified by the presence of an h3
            # with specific text
            if navigator.find("h3", text="Accessing private documents"):
                raise NotLoggedInException()

            # check if we have the default page (DCC redirects here for all
            # unrecognised requests)
            if navigator.find("strong", text="Search for Documents by"):
                raise UnrecognisedDccRecordException()

            # check if we have the error page
            if navigator.find("dt", class_="Error"):
                # we have an error, but what is its message?
                if navigator.find(
                    "dd",
                    text=re.compile(
                        "User .*? is not authorized to view this document."
                    ),
                ):
                    # unauthorised to view
                    raise UnauthorisedAccessException()

            # unknown error
            raise UnknownDccErrorException()

        if not self.root.attrib["project"] == "LIGO":
            # invalid DCC document
            raise InvalidDCCXMLDocumentException()

        self.doc = self.root[0]
        self.docrev = self.doc[0]

    def extract_dcc_number(self):
        t = self.docrev.find("dccnumber").text[0]
        n = self.docrev.find("dccnumber").text[1:]
        v = self.docrev.attrib["version"]
        return dcc.record.DccNumber(t, n, v)

    def extract_docid(self):
        return dcc.record.DccDocId(self.docrev.attrib["docid"])

    def extract_title(self):
        return self.docrev.find("title").text

    def extract_authors(self):
        authors = []
        for a in self.docrev.findall("author"):
            name = a.find("fullname").text
            try:
                enum = a.find("employeenumber").text
            except AttributeError:
                enum = None
            authors.append(dcc.record.DccAuthor(name, enum))
        return authors

    def extract_abstract(self):
        return str(self.docrev.find("abstract").text)

    def extract_keywords(self):
        return [str(k.text) for k in self.docrev.findall("keyword")]

    def extract_note(self):
        return str(self.docrev.find("note").text)

    def extract_publication_info(self):
        return str(self.docrev.find("publicationinfo").text)

    def extract_journal_reference(self):
        ref = self.docrev.find("reference")

        if ref:
            # journal reference present

            # get URL attribute
            if "href" in ref.attrib.keys():
                url = ref.attrib["href"]
            else:
                url = None

            # get contained fields
            citation = ref.find("citation").text
            journal = ref.find("journal").text
            volume = ref.find("volume").text
            page = ref.find("page").text

            ref = dcc.record.DccJournalRef(journal, volume, page, citation, url)

        return ref

    def extract_other_version_numbers(self):
        # use set to remove duplicates, but return a list
        return list(
            set([int(r.attrib["version"]) for r in self.docrev.find("otherversions")])
        )

    def extract_revision_dates(self):
        # DCC dates use the Pacific timezone
        pacific = pytz.timezone("US/Pacific")

        # parse modified date string localised to Pacific Time
        modified = pacific.localize(
            datetime.strptime(self.docrev.attrib["modified"], "%Y-%m-%d %H:%M:%S")
        )

        # other dates aren't in XML yet
        return (None, modified, None)

    def extract_attached_files(self):
        files = []
        for f in self.docrev.findall("file"):
            name = f.find("name").text
            try:
                title = f.find("description").text
            except AttributeError:
                title = name
            url = f.attrib["href"]
            files.append(dcc.record.DccFile(title, name, url))
        return files

    def extract_related_ids(self):
        return [
            dcc.record.DccDocId.parse_from_xref(f)
            for f in self.docrev.findall("xrefto")
        ]

    def extract_referencing_ids(self):
        return [
            dcc.record.DccDocId.parse_from_xref(f)
            for f in self.docrev.findall("xrefby")
        ]


class DccXmlUpdateParser(object):
    """Represents a parser for DCC XMLUpdate responses"""

    def __init__(self, content):
        """Instantiates a DccXmlUpdateParser with the provided page content

        :param content: DCC XMLUpdate response HTML

        """
        self.logger = logging.getLogger("xmlupdate-parser")
        self.content = content

    def validate(self):
        # get an HTML navigator object for the response
        navigator = bs(self.content, "html.parser")

        # accept if the page reports a successful modification
        if navigator.find(string=re.compile(".*You were successful.*")):
            return

        # check if we have the login page, specified by the presence of an h3
        # with specific text
        if navigator.find("h3", text="Accessing private documents"):
            raise NotLoggedInException()

        # check if we have the default page (DCC redirects here for all
        # unrecognised requests)
        if navigator.find("strong", text="Search for Documents by"):
            raise UnrecognisedDccRecordException()

        # check if we have the error page
        if navigator.find("dt", class_="Error"):
            # we have an error, but what is its message?
            if navigator.find("dd", text=re.compile(".* is invalid.*")):
                # record number not valid
                raise DccNumberNotFoundException()
            if navigator.find("dd", text=re.compile(".* is not modifiable by user.*")):
                # unauthorised to update
                raise UnauthorisedAccessException()

        # unknown error
        raise UnknownDccErrorException()


class DccNumberNotFoundException(Exception):
    """Exception for when a DCC number is not found"""

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


class InvalidDCCXMLDocumentException(Exception):
    """Exception for when a document is not a valid LIGO DCC XML record"""

    # error message given to user
    message = "The document was retrieved, but is not a valid LIGO DCC XML \
record"

    def __init__(self, *args, **kwargs):
        """Constructs an invalid LIGO DCC XML record exception"""

        # call parent constructor with the error message
        super(InvalidDCCXMLDocumentException, self).__init__(
            self.message, *args, **kwargs
        )


class UnknownDccErrorException(Exception):
    """Exception for when an unknown error is reported by the DCC"""

    # error message given to user
    message = "An unknown error occurred; please report this to the developers"

    def __init__(self, *args, **kwargs):
        """Constructs an unknown exception"""

        # call parent constructor with the error message
        super(UnknownDccErrorException, self).__init__(self.message, *args, **kwargs)
