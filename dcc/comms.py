# -*- coding: utf-8 -*-

"""Communication classes"""

import urllib2
import abc
import logging
import dcc.record as record
import dcc.patterns as patterns

class Fetcher(object):
    """Represents a collection of tools to communicate with the DCC server"""

    # abstract method
    __metaclass__ = abc.ABCMeta

    def fetch_dcc_record(self, dcc_number):
        """Fetches the DCC record specified by the provided number

        :param dcc_number: DCC number object representing record (or, alternatively, the string)
        """

        # create DCC number object if necessary
        if isinstance(dcc_number, str):
            dcc_number = record.DccNumber(dcc_number)

        # create the DCC URL
        url = self._build_dcc_url(dcc_number)

        # get the page contents
        contents = self._get_url_contents(url)

        # parse new DCC record
        dcc_record = patterns.DccRecordParser(contents).to_record()

        # make sure its number matches the request
        if dcc_record.dcc_number != dcc_number:
            raise DifferentDccRecordException()

        return dcc_record

    @abc.abstractmethod
    def _build_dcc_url(self, dcc_number):
        """Builds the URL representing the specified DCC number"""

        pass

    @abc.abstractmethod
    def _get_url_contents(self, url):
        """Fetches the specified contents at the specified URL"""

        pass

class HttpFetcher(Fetcher):
    """Represents a fetcher using HTTP"""

    # DCC servers, in order of preference
    servers = ["dcc.ligo.org", "dcc-backup.ligo.org", "dcc-lho.ligo.org", "dcc-llo.ligo.org"]

    # protocol
    protocol = "http"

    # dict to hold downloaded records
    retrieved_dcc_records = {}

    def __init__(self, cookies):
        """Instantiates an HTTP fetcher using the specified cookies

        :param cookies: cookies set by DCC during login, to allow the active session to be used
        """

        # create logger
        self.logger = logging.getLogger("http-fetcher")

        self.cookies = cookies

    def _build_dcc_url(self, dcc_number):
        """Builds a DCC URL given the specified DCC number"""

        # create URL
        url = self.protocol + "://" + self.servers[0] + "/" + str(dcc_number)

        # add a version if present
        if dcc_number.version is not None:
            url += record.DccNumber.get_version_suffix(dcc_number.version)

        return url

    def _get_url_contents(self, url):
        opener = urllib2.build_opener()
        opener.addheaders.append(["Cookie", self.cookies])

        self.logger.info("Fetching document at URL %s", url)
        stream = opener.open(url)

        self.logger.info("Reading document content")
        return stream.read()

class DifferentDccRecordException(Exception):
    """Exception for when a different DCC record is retrieved compared to the requested one"""
    pass
