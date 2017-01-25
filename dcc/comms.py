# -*- coding: utf-8 -*-

"""Communication classes

TODO: this should also do caching
"""

from __future__ import unicode_literals

import sys
import urllib2
import abc
import logging
import dcc.record
import dcc.patterns

class Fetcher(object):
    """Represents a collection of tools to communicate with the DCC server"""

    # abstract method
    __metaclass__ = abc.ABCMeta

    def __init__(self, progress_hook=None):
        """Instantiates a fetcher

        :param progress_hook: callable to send download progress
        """

        self.progress_hook = progress_hook

    def get_url(self, dcc_number):
        """Return the record url for DCC number

        :param dcc_number: DCC number
        """

        # create URL, fetch it and return it
        return self._build_dcc_base_url(dcc_number)

    def fetch_record_page(self, dcc_number):
        """Fetches the DCC record page specified by the provided number

        :param dcc_number: DCC number to fetch record for
        """

        # create URL, fetch it and return it
        return self._get_url_contents(self._build_dcc_record_url(dcc_number))

    def fetch_author_page(self, author):
        """Fetches the page of the author specified

        :param author: author to fetch page for
        """

        # create URL, fetch it then return it
        return self._get_url_contents(self._build_dcc_author_url(author))

    def fetch_file_data(self, dcc_file):
        """Fetches the file data associated with the specified file

        :param dcc_file: file to fetch data for
        """

        # fetch and return the data at the file's URL
        return self._get_url_contents(dcc_file.url)

    @abc.abstractmethod
    def _build_dcc_record_url(self, dcc_number):
        """Builds the URL representing the specified DCC number"""

        pass

    @abc.abstractmethod
    def _build_dcc_author_url(self, author):
        """Builds the URL representing the specified author"""

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
    protocol = "https"

    # download chunk size
    chunk_size = 8192

    def __init__(self, cookies):
        """Instantiates an HTTP fetcher using the specified cookies

        :param cookies: cookies set by DCC during login, to allow the active session to be used
        """

        # create logger
        self.logger = logging.getLogger("http-fetcher")

        # set cookies
        self.cookies = cookies

        # create empty dict to hold downloaded records
        self.retrieved_dcc_records = {}

    def _build_dcc_base_url(self, dcc_number):
        """Builds a DCC record base URL given the specified DCC number

        :param dcc_number: number of DCC record to download
        """

        return '{protocol}://{server}/{path}'.format(
            protocol=self.protocol,
            server=self.get_preferred_server(),
            path=dcc_number.get_url_path(),
            )

    def _build_dcc_record_url(self, dcc_number):
        """Builds a DCC record URL given the specified DCC number

        :param dcc_number: number of DCC record to download
        """

        # create and return URL
        # query string asks for the XML version of the document
        return '{base}/{query}'.format(
            base=self._build_dcc_base_url(dcc_number),
            query='of=xml',
            )

    def _build_dcc_author_url(self, author):
        """Builds a DCC author page URL given the specified author

        :param author: author to download
        """

        # create and return URL
        return self.protocol + "://" + self.get_preferred_server() + \
        "/cgi-bin/private/DocDB/ListBy?authorid=" + unicode(author.uid)

    def get_preferred_server(self):
        """Returns the user's preferred server"""

        # for now, just return the main one
        return self.servers[0]

    def _get_url_contents(self, url):
        """Gets the contents at the specified URL

        :param url: URL to retrieve
        """

        # create a URL reader
        opener = urllib2.build_opener()

        # set the cookies
        opener.addheaders.append(["Cookie", self.cookies])

        self.logger.info("Fetching contents at URL %s", url)

        # open a stream to the URL
        stream = opener.open(url)

        # get content size
        content_length_header = stream.info().getheader('Content-Length')

        # if the content length header is not specified, just return the full data
        if content_length_header is None:
            self.logger.debug("No download progress information available")

            # return content
            return stream.read()
        elif self.progress_hook is None:
            # user doesn't want progress, so just return the content
            return stream.read()

        # calculate content length in bytes
        total_size = int(content_length_header.strip())

        # initial download progress
        bytes_so_far = 0

        # list of bytes
        data = []

        # loop until the data is fully retrieved
        while True:
            # read the next chunk
            chunk = stream.read(self.chunk_size)

            # add the number of bytes retrieved to the sum
            bytes_so_far += len(chunk)

            # an empty chunk means we've got the data
            if not chunk:
                break

            # add data to list
            data += chunk

            if self.progress_hook:
                self.progress_hook(bytes_so_far, self.chunk_size, total_size)

        # join up the bytes into a string and return
        return b"".join(data)
