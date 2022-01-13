"""Communication with the DCC.

TODO: this should also do caching
"""

import abc
import logging
from ciecplib import Session as CIECPSession

LOGGER = logging.getLogger(__name__)


class DCCHTTPFetcher(metaclass=abc.ABCMeta):
    """An HTTP fetcher for DCC documents."""

    # Transport protocol.
    protocol = "https"

    def __init__(self, host, **kwargs):
        super().__init__(**kwargs)
        self.host = host

    @abc.abstractmethod
    def get(self, url):
        raise NotImplementedError

    def _dcc_record_url(self, dcc_number, xml=True):
        """Builds a DCC record base URL given the specified DCC number.

        :param dcc_number: number of DCC record to download
        :param xml: whether to append the XML request string
        """

        return self._build_dcc_url(dcc_number.url_path(xml=xml))

    def fetch_record_page(self, dcc_number):
        """Fetches the DCC record page specified by the provided number.

        :param dcc_number: DCC number to fetch record for
        """
        response = self.get(self._dcc_record_url(dcc_number))
        response.raise_for_status()
        return response

    def fetch_file(self, dcc_file, stream=True):
        """Fetch the file associated with the specified file.

        :param dcc_file: file to stream data for
        """
        response = self.get(dcc_file.url, stream=stream)
        response.raise_for_status()
        return response

    def update_record_metadata(
        self,
        dcc_number,
        title=None,
        abstract=None,
        keywords=None,
        note=None,
        related=None,
        authors=None,
    ):
        """Updates metadata for the DCC record specified by the provided number.

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

        # Build DCC "Bulk Modify" request URL.
        dcc_update_metadata_url = self._build_dcc_url("cgi-bin/private/DocDB/XMLUpdate")

        # Prepare form data dict with the requested updates.
        data = self._build_dcc_metadata_form(
            title=title,
            abstract=abstract,
            keywords=keywords,
            note=note,
            related=related,
            authors=authors,
        )
        data["DocumentsField"] = dcc_number.string_repr(version=False)
        data["DocumentChange"] = "Change Latest Version"

        # post form data and return server's response
        return self._post_url_form_data(dcc_update_metadata_url, data)

    def _build_dcc_metadata_form(
        self,
        title=None,
        abstract=None,
        keywords=None,
        note=None,
        related=None,
        authors=None,
    ):
        """Builds form data representing the specified metadata update."""

        fields = [
            (title, "TitleField", "TitleChange"),
            (abstract, "AbstractField", "AbstractChange"),
            (keywords, "KeywordsField", "KeywordsChange"),
            (note, "NotesField", "NotesChange"),
            (related, "RelatedDocumentsField", "RelatedDocumentsChange"),
            (authors, "authormanual", "AuthorsChange"),
        ]

        data = dict()
        for field_data, field_name, field_change_name in fields:
            if field_data is not None:
                data[field_name] = field_data
                data[field_change_name] = "Replace"
            else:
                data[field_name] = ""
                data[field_change_name] = "Append"

        return data

    def _build_dcc_url(self, path=""):
        """Builds a DCC URL given path."""
        if path:
            path = f"/{path}"

        return f"{self.protocol}://{self.host}{path}"

    def _build_dcc_author_url(self, author):
        """Builds a DCC author page URL given the specified author.

        :param author: author to download
        """

        return self._build_dcc_url(
            f"cgi-bin/private/DocDB/ListBy?authorid={author.uid}"
        )

    def _post_url_form_data(self, url, data):
        """Posts the specified form data to the specified URL.

        Returns the response of the server

        :param url: URL to post
        :param data: dict containing form data
        """

        import urllib

        # obtain cookies for DCC access
        opener = self._build_url_opener()

        LOGGER.info(f"Posting form data to {url}")

        # convert dict to URL-encoded bytes
        data = urllib.parse.urlencode(data).encode()

        # POST request is used when form data is supplied
        req = urllib.request.Request(url, data)

        # read and return the server's response
        return opener.open(req).read()


class DCCSession(CIECPSession, DCCHTTPFetcher):
    """A SAML/ECP-authenticated DCC HTTP fetcher."""
