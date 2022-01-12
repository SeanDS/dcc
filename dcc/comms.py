# -*- coding: utf-8 -*-

"""Communication classes

TODO: this should also do caching
"""

import sys
import os
import subprocess
import abc
import logging
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar

class Fetcher(object, metaclass=abc.ABCMeta):
    """Represents a collection of tools to communicate with the DCC server"""

    def __init__(self, progress_hook=None):
        """Instantiates a fetcher

        :param progress_hook: callable to send download progress
        """

        self.progress_hook = progress_hook

    def get_record_url(self, *args, **kwargs):
        """Return the record url for DCC number"""

        # create URL, fetch it and return it
        return self._build_dcc_record_url(*args, **kwargs)

    def fetch_record_page(self, dcc_number):
        """Fetches the DCC record page specified by the provided number

        :param dcc_number: DCC number to fetch record for
        """

        # create URL, fetch it and return it
        return self._get_url_contents(self._build_dcc_record_url(dcc_number))

    def fetch_file_data(self, dcc_file):
        """Fetches the file data associated with the specified file

        :param dcc_file: file to fetch data for
        """

        # fetch and return the data at the file's URL
        return self._get_url_contents(dcc_file.url)

    def update_record_metadata(self, dcc_number, title=None, abstract=None,
                               keywords=None, note=None, related=None, authors=None):
        """Updates metadata for the DCC record specified by the provided number

        The version (if any) of the provided DCC number is ignored.  Only the latest
        version of the record is updated.

        Returns the response of the server to the update request

        :param dcc_number: DCC number to update metadata for
        :param title: metadata field contents (None to leave unchanged)
        :param abstract: metadata field contents (None to leave unchanged)
        :param keywords: metadata field contents (None to leave unchanged)
        :param note: metadata field contents (None to leave unchanged)
        :param related: metadata field contents (None to leave unchanged)
        :param authors: metadata field contents (None to leave unchanged)
        """

        # build DCC "Bulk Modify" request URL
        dcc_update_metadata_url = self._build_dcc_url('cgi-bin/private/DocDB/XMLUpdate')

        # prepare form data dict with the requested updates
        data = self._build_dcc_metadata_form(title=title, abstract=abstract,
                                             keywords=keywords, note=note,
                                             related=related, authors=authors)
        data['DocumentsField'] = dcc_number.string_repr(version=False)
        data['DocumentChange'] = "Change Latest Version"

        # post form data and return server's response
        return self._post_url_form_data(dcc_update_metadata_url, data)

    @abc.abstractmethod
    def _build_dcc_record_url(self, dcc_number, xml=True):
        """Builds the URL representing the specified DCC number"""

        pass

    @abc.abstractmethod
    def _build_dcc_author_url(self, author):
        """Builds the URL representing the specified author"""

        pass

    def _build_dcc_metadata_form(self, title=None, abstract=None, keywords=None,
                                 note=None, related=None, authors=None):
        """Builds form data representing the specified metadata update"""

        fields = [
            (title, 'TitleField', 'TitleChange'),
            (abstract, 'AbstractField', 'AbstractChange'),
            (keywords, 'KeywordsField', 'KeywordsChange'),
            (note, 'NotesField', 'NotesChange'),
            (related, 'RelatedDocumentsField', 'RelatedDocumentsChange'),
            (authors, 'authormanual', 'AuthorsChange'),
            ]

        data = dict()
        for field_data, field_name, field_change_name in fields:
            if field_data is not None:
                data[field_name] = field_data
                data[field_change_name] = 'Replace'
            else:
                data[field_name] = ''
                data[field_change_name] = 'Append'

        return data

    @abc.abstractmethod
    def _get_url_contents(self, url):
        """Fetches the specified contents at the specified URL"""

        pass

    @abc.abstractmethod
    def _post_url_form_data(self, url, data):
        """Posts the specified form data to the specified URL"""

        pass

class HttpFetcher(Fetcher):
    """Represents a fetcher using HTTP"""

    # DCC servers, in order of preference
    servers = ["dcc.ligo.org", "dcc-backup.ligo.org", "dcc-lho.ligo.org", "dcc-llo.ligo.org"]

    # protocol
    protocol = "https"

    # ecp cookie file
    # FIXME: should we use a special cookie file for this app?
    ecp_cookie_path = os.getenv('ECP_COOKIE_FILE', '/tmp/ecpcookie.u{}'.format(os.getuid()))

    # download chunk size
    chunk_size = 8192

    def __init__(self, *args, **kwargs):
        """Instantiates an HTTP fetcher"""

        # create logger
        self.logger = logging.getLogger("http-fetcher")

        # call parent constructor
        super(HttpFetcher, self).__init__(*args, **kwargs)

    def get_preferred_server(self):
        """Returns the user's preferred server"""

        # for now, just return the main one
        return self.servers[0]

    def _build_dcc_url(self, path=''):
        """Builds a DCC URL given path"""
        if path:
            path = '/{}'.format(path)
        return '{protocol}://{server}{path}'.format(
            protocol=self.protocol,
            server=self.get_preferred_server(),
            path=path,
            )

    def _build_dcc_record_url(self, dcc_number, xml=True):
        """Builds a DCC record base URL given the specified DCC number

        :param dcc_number: number of DCC record to download
        :param xml: whether to append the XML request string
        """

        return self._build_dcc_url(dcc_number.get_url_path(xml=xml))

    def _build_dcc_author_url(self, author):
        """Builds a DCC author page URL given the specified author

        :param author: author to download
        """

        return self._build_dcc_url("cgi-bin/private/DocDB/ListBy?authorid=" + str(author.uid))

    def ecp_cookie_init(self):
        """Execute ecp-cookie-init to fetch a new session cookie"""
        # This is meant for debugging authentication, so that an
        # expired cookie can be provided and it won't be overwritten.
        if os.getenv('ECP_COOKIE_FILE'):
            return
        dcc_url = self._build_dcc_url('dcc')
        self.logger.info("Fetching cookies for: %s", dcc_url)
        cmd = ['ecp-cookie-init', '-k', '-q', '-n',
               '-c', self.ecp_cookie_path,
               dcc_url]
        self.logger.debug(' '.join(cmd))
        ecp_ret = subprocess.run(cmd,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        if ecp_ret.returncode != 0:
            klist_ret = subprocess.run(['klist'],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            if klist_ret.returncode != 0:
                raise KerberosError()
            else:
                ecp_ret.check_returncode()

    def _build_url_opener(self):
        """Returns an URL opener with cookies loaded for DCC access"""

        if os.path.exists(self.ecp_cookie_path):
            self.logger.info("Found cookie file: %s", self.ecp_cookie_path)
        else:
            self.ecp_cookie_init()

        # create cookie manager and fetch ecp cookies
        cookie_jar = ECPCookieJar(self.ecp_cookie_path)

        # load from the file
        # NOTE: ignore_discard must be true otherwise the session cookie is not loaded
        cookie_jar.load(ignore_discard=True)

        # create cookie processor
        cookie_processor = urllib.request.HTTPCookieProcessor(cookie_jar)

        # return an opener with the cookie processor
        return urllib.request.build_opener(cookie_processor)

    def _get_url_contents(self, url):
        """Gets the contents at the specified URL

        :param url: URL to retrieve
        """

        # obtain cookies for DCC access
        opener = self._build_url_opener()

        self.logger.info("Fetching contents at URL %s", url)

        # open a stream to the URL
        stream = opener.open(url)

        # get content size
        content_length_header = stream.getheader('Content-Length')

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

    def _post_url_form_data(self, url, data):
        """Posts the specified form data to the specified URL

        Returns the response of the server

        :param url: URL to post
        :param data: dict containing form data
        """

        # obtain cookies for DCC access
        opener = self._build_url_opener()

        self.logger.info("Posting form data to URL %s", url)

        # convert dict to URL-encoded bytes
        data = urllib.parse.urlencode(data).encode()

        # POST request is used when form data is supplied
        req = urllib.request.Request(url, data)

        # read and return the server's response
        return opener.open(req).read()

class ECPCookieJar(http.cookiejar.MozillaCookieJar):
    """Alternate cookiejar parser that replaces expiry date of 0 with an empty \
    string to avoid Python parsing issue when using ecp-cookie-init"""

    def _really_load(self, f, filename, ignore_discard, ignore_expires):
        """Overridden version of http.cookiejar.MozillaCookieJar._really_load

        This has the same behaviour as http.cookiejar.MozillaCookieJar except
        that when it searches for session cookies generated by ecp-cookie-init
        in the /tmp/ecpcookie.u{uid} file, it allows both empty strings and "0"
        to represent cookies due to expire in the current session. The default
        behaviour of this method is to only accept emptry strings and not "0",
        but ecp-cookie-init uses "0".

        Additionally the ignore_discard parameter must be set to True to allow
        this new behaviour to take effect.
        """

        import time

        now = time.time()

        magic = f.readline()
        if not self.magic_re.search(magic):
            raise http.cookiejar.LoadError(
                "%r does not look like a Netscape format cookies file" %
                filename)

        try:
            while 1:
                line = f.readline()
                if line == "": break

                # last field may be absent, so keep any trailing tab
                if line.endswith("\n"): line = line[:-1]

                # remove #HttpOnly_ prefix
                if line.strip().startswith("#HttpOnly_"):
                    line = line[len("#HttpOnly_"):]

                # skip comments and blank lines XXX what is $ for?
                if (line.strip().startswith(("#", "$")) or
                    line.strip() == ""):
                    continue

                domain, domain_specified, path, secure, expires, name, value = \
                        line.split("\t")
                secure = (secure == "TRUE")
                domain_specified = (domain_specified == "TRUE")

                if name == "":
                    # cookies.txt regards 'Set-Cookie: foo' as a cookie
                    # with no name, whereas http.cookiejar regards it as a
                    # cookie with no value.
                    name = value
                    value = None

                initial_dot = domain.startswith(".")
                assert domain_specified == initial_dot

                discard = False

                # support both empty and 0 for session cookies
                if expires == "" or "0":
                    expires = None
                    discard = True

                # assume path_specified is false
                c = http.cookiejar.Cookie(0, name, value,
                           None, False,
                           domain, domain_specified, initial_dot,
                           path, False,
                           secure,
                           expires,
                           discard,
                           None,
                           None,
                           {})

                if not ignore_discard and c.discard:
                    continue

                if not ignore_expires and c.is_expired(now):
                    continue

                self.set_cookie(c)

        except OSError:
            raise
        except Exception:
            http.cookiejar._warn_unhandled_exception()

            raise http.cookiejar.LoadError(\
                            "invalid Netscape format cookies file %r: %r" %
                            (filename, line))

class KerberosError(Exception):
    """Exception for missing Kerberos credentials"""
    pass
