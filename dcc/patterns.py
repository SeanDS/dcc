# -*- coding: utf-8 -*-

"""Pattern matching classes"""

from __future__ import unicode_literals

import abc
import logging
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET
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
            raise DccNumberNotFoundException()
        assert self.root.attrib['project'] == 'LIGO'
        self.doc = self.root[0]
        self.docrev = self.doc[0]

    def extract_dcc_number(self):
        t = self.docrev.find('dccnumber').text[0]
        n = self.docrev.find('dccnumber').text[1:]
        v = self.docrev.attrib['version']
        return dcc.record.DccNumber(t,n,v)

    def extract_title(self):
        return self.docrev.find('title').text

    def extract_authors(self):
        authors = []
        for a in self.docrev.findall('author'):
            name = a.find('fullname').text
            try:
                enum = a.find('employeenumber').text
            except AttributeError:
                enum = None
            authors.append(dcc.record.DccAuthor(name, enum))
        return authors

    def extract_other_version_numbers(self):
        return [r.attrib['version'] for r in self.docrev.find('otherversions')]

    def extract_revision_dates(self):
        return (None, self.docrev.attrib['modified'], None)

    def extract_attached_files(self):
        files = []
        for f in self.docrev.findall('file'):
            name = f.find('name').text
            try:
                title = f.find('description').text
            except AttributeError:
                title = name
            url = f.attrib['href']
            files.append(dcc.record.DccFile(title, name, url))
        return files

    def extract_related_numbers(self):
        # FIXME: DCC NEEDS TO ADD THIS TO XML
        return []

    def extract_referencing_numbers(self):
        return [f.attrib['docid'] for f in self.docrev.findall('xrefby')]

class DccAuthorPageParser(object):
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

    def extract_dcc_numbers(self):
        """Extracts the author's records from the page"""

        # get a navigator object for the record
        navigator = self._get_content_navigator()

        # empty list of numbers
        dcc_numbers = []

        # get the record table
        record_table = navigator.find("table", class_="Alternating DocumentList sortable")

        # if there is no related div, return
        if record_table is None:
            return dcc_numbers

        # extract doc ID table cells
        doc_ids = record_table.find_all("td", class_="Docid")

        # if there are no doc IDs, return
        if doc_ids is None:
            return dcc_numbers

        # loop over doc IDs
        for doc_id in doc_ids:
            # extract the anchor element
            number_anchor = doc_id.find("a")

            # if there is no anchor, skip
            if number_anchor is None:
                continue

            # find the DCC number in the anchor
            dcc_number = self.dcc_patterns.get_dcc_number_from_string( \
            number_anchor.text)

            # add to list
            dcc_numbers.append(dcc_number)

        # return list of DCC numbers
        return dcc_numbers

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
