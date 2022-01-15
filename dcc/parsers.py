"""Record parsing."""


import re
from functools import cached_property
from datetime import datetime
import xml.etree.ElementTree as ET
import pytz
from bs4 import BeautifulSoup as bs
from .exceptions import (
    NotLoggedInError,
    UnrecognisedDCCRecordError,
    UnauthorisedError,
    UnknownError,
)


class DCCRecordParser:
    """A parser for DCC XML documents.

    Parameters
    ----------
    content : str
        The response body.
    """

    def __init__(self, content):
        try:
            self.root = ET.fromstring(content)
        except ET.ParseError:
            # This is not an XML document. Do we have an error page instead? Use the
            # HTML parser to find out.

            # Get an HTML navigator object for the record.
            navigator = bs(content, "html.parser")

            # Check if we have the login page, specified by the presence of an h3 with
            # specific text.
            if navigator.find("h3", text="Accessing private documents"):
                raise NotLoggedInError()

            # Check if we have the default page (DCC redirects here for all unrecognised
            # requests).
            if navigator.find("strong", text="Search for Documents by"):
                raise UnrecognisedDCCRecordError()

            # Check if we have the error page.
            if navigator.find("dt", class_="Error"):
                # We have an error, but what is its message?
                if navigator.find(
                    "dd",
                    text=re.compile(
                        "User .*? is not authorized to view this document."
                    ),
                ):
                    # Unauthorised.
                    raise UnauthorisedError()

            raise UnknownError()

        if not self.root.attrib["project"] == "LIGO":
            # Invalid DCC document.
            raise UnrecognisedDCCRecordError()

        self.doc = self.root[0]
        self.docrev = self.doc[0]

    @cached_property
    def dcc_number_pieces(self):
        t = self.docrev.find("dccnumber").text[0]
        n = self.docrev.find("dccnumber").text[1:]
        v = self.docrev.attrib["version"]
        return t, n, v

    @cached_property
    def docid(self):
        return self.docrev.attrib["docid"]

    @cached_property
    def title(self):
        return self.docrev.find("title").text

    @cached_property
    def authors(self):
        for a in self.docrev.findall("author"):
            name = a.find("fullname").text

            try:
                enum = a.find("employeenumber").text
            except AttributeError:
                enum = None

            yield name, enum

    @cached_property
    def abstract(self):
        return self.docrev.find("abstract").text

    @cached_property
    def keywords(self):
        return [k.text for k in self.docrev.findall("keyword")]

    @cached_property
    def note(self):
        return self.docrev.find("note").text

    @cached_property
    def publication_info(self):
        return self.docrev.find("publicationinfo").text

    @cached_property
    def journal_reference(self):
        ref = self.docrev.find("reference")

        if not ref:
            return

        journal = ref.find("journal").text
        volume = ref.find("volume").text
        page = ref.find("page").text
        citation = ref.find("citation").text
        url = ref.attrib.get("href")

        return journal, volume, page, citation, url

    @cached_property
    def other_version_numbers(self):
        return set(
            [int(r.attrib["version"]) for r in self.docrev.find("otherversions")]
        )

    @cached_property
    def revision_dates(self):
        # DCC dates use the Pacific timezone
        pacific = pytz.timezone("US/Pacific")

        # parse modified date string localised to Pacific Time
        modified = pacific.localize(
            datetime.strptime(self.docrev.attrib["modified"], "%Y-%m-%d %H:%M:%S")
        )

        # other dates aren't in XML yet
        return None, modified, None

    @cached_property
    def attached_files(self):
        for file_ in self.docrev.findall("file"):
            name = file_.find("name").text

            try:
                title = file_.find("description").text
            except AttributeError:
                title = name

            url = file_.attrib["href"]
            yield title, name, url

    @cached_property
    def related_ids(self):
        return self._extract_refs("xrefto")

    @cached_property
    def referencing_ids(self):
        return self._extract_refs("xrefby")

    def _extract_refs(self, field):
        for field in self.docrev.findall(field):
            # Extract the DCC number.
            yield field.attrib["alias"]


class DCCXMLUpdateParser:
    """A parser for DCC XMLUpdate responses.

    Parameters
    ----------
    content : str
        The response body.
    """

    def __init__(self, content):
        # Get an HTML navigator object for the record.
        navigator = bs(content, "html.parser")

        # Accept if the page reports a successful modification.
        if navigator.find(string=re.compile(".*You were successful.*")):
            return

        # Check if we have the login page, specified by the presence of an h3 with
        # specific text.
        if navigator.find("h3", text="Accessing private documents"):
            raise NotLoggedInError()

        # Check if we have the default page (DCC redirects here for all unrecognised
        # requests).
        if navigator.find("strong", text="Search for Documents by"):
            raise UnrecognisedDCCRecordError()

        # Check if we have the error page.
        if navigator.find("dt", class_="Error"):
            # We have an error, but what is its message?
            if navigator.find("dd", text=re.compile(".* is invalid.*")):
                # Record number not valid.
                raise ValueError("record number not valid")
            if navigator.find("dd", text=re.compile(".* is not modifiable by user.*")):
                # Unauthorised to update.
                raise UnauthorisedError()

        raise UnknownError()