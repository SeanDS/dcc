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

    def fetch_dcc_record(self, dcc_number, download_files=False):
        """Fetches the DCC record specified by the provided number

        :param dcc_number: DCC number object representing record (or, alternatively, the string)
        :param download_files: whether to download the files attached to the record
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

        # download the files associated with the record, if requested
        if download_files:
            self._download_record_files(dcc_record)

        return dcc_record

    @abc.abstractmethod
    def _build_dcc_url(self, dcc_number):
        """Builds the URL representing the specified DCC number"""

        pass

    @abc.abstractmethod
    def _get_url_contents(self, url):
        """Fetches the specified contents at the specified URL"""

        pass

    @abc.abstractmethod
    def _download_record_files(self, dcc_record):
        """Fetches the files attached to the specified record

        :param dcc_record: DCC record to fetch files for
        """

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
        url = self.protocol + "://" + self.servers[0] + "/" + dcc_number.get_url_path()

        return url

    def _get_url_contents(self, url):
        opener = urllib2.build_opener()
        opener.addheaders.append(["Cookie", self.cookies])

        self.logger.info("Fetching document at URL %s", url)
        stream = opener.open(url)

        self.logger.info("Reading document content")
        return stream.read()

    def _download_record_files(self, dcc_record):
        """Fetches the files attached to the specified record

        :param dcc_record: DCC record to fetch files for
        """

        # count files
        total_count = len(dcc_record.files)

        # current file count
        current_count = 1

        self.logger.info("Fetching files...")

        # loop over files in this record
        for dcc_file in dcc_record.files:
            self.logger.info("(%d/%d) Fetching %s", current_count, total_count, dcc_file)

            # get the file contents
            data = self._get_url_contents(dcc_file.url)

            # attach data to file
            dcc_file.set_data(data)

            # increment counter
            current_count += 1

        self.logger.info("Finished fetch")

class DifferentDccRecordException(Exception):
    """Exception for when a different DCC record is retrieved compared to the requested one"""
    pass
