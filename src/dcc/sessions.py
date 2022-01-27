"""Communication with the DCC."""

import abc
import logging
from requests import Session
from ciecplib import Session as CIECPSession
from .env import DEFAULT_HOST, DEFAULT_IDP

LOGGER = logging.getLogger(__name__)


def default_session(authenticated=False):
    """Create a DCC session using the default host and identity provider.

    Parameters
    ----------
    authenticated : :class:`bool`, optional
        Whether to make the session an authenticated one. Defaults to False.

    Returns
    -------
    :class:`.DCCAuthenticatedSession`
        The default session.
    """
    if authenticated:
        return DCCAuthenticatedSession(host=DEFAULT_HOST, idp=DEFAULT_IDP)
    else:
        return DCCUnauthenticatedSession(host=DEFAULT_HOST)


class DCCSession(metaclass=abc.ABCMeta):
    """A DCC HTTP fetcher.

    Parameters
    ----------
    host : str
        The DCC host to use.

    stream_hook : callable, optional
        Function taking a stream type, the item being streamed, and a
        :class:`requests.Response` object from a streamed GET or POST request, yielding
        its body content. This can be used to implement download progress bars,
        interactive skipping of downloads, etc.
    """

    # Transport protocol.
    protocol = "https"

    # Stream types.
    STREAM_FILE = 1

    def __init__(
        self,
        host,
        *,
        stream_hook=None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if stream_hook is None:

            def stream_hook(_a, _b, response):
                yield from response

        self.host = host
        self.stream_hook = stream_hook

    def fetch_record_page(self, dcc_number):
        """Fetch a DCC record page.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC record.

        Returns
        -------
        :class:`requests.Response`
            The HTTP response.
        """
        url = self.dcc_record_url(dcc_number)
        LOGGER.debug(f"GET record at {url}")
        response = self.get(url)
        response.raise_for_status()
        return response

    def fetch_file_contents(self, dcc_file):
        """Fetch the remote contents of the specified file.

        Parameters
        ----------
        dcc_file : :class:`.DCCFile`
            The DCC file to fetch.

        Yields
        ------
        :class:`bytes`
            The next chunk of the file.
        """
        url = dcc_file.url
        LOGGER.debug(f"GET file at {url}")
        response = self.get(url, stream=True)
        response.raise_for_status()
        return self.stream_hook(self.STREAM_FILE, dcc_file, response)

    def update_record_metadata(self, dcc_record):
        """Update metadata for the DCC record specified by the provided number.

        The version (if any) of the provided DCC number is ignored. Only the latest
        version of the record is updated.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC record.

        Returns
        -------
        :class:`requests.Response`
            The HTTP response.
        """

        # Build DCC "Bulk Modify" request URL.
        dcc_update_metadata_url = self._build_dcc_url("cgi-bin/private/DocDB/XMLUpdate")

        # Prepare form data dict with the requested updates.
        data = self._build_dcc_metadata_form(dcc_record)

        data["DocumentsField"] = dcc_record.dcc_number.format(version=False)
        data["DocumentChange"] = "Change Latest Version"

        # Submit form data.
        url = dcc_update_metadata_url
        LOGGER.debug(f"POST record update at {url} with data {data}")
        response = self.post(url, data)
        response.raise_for_status()
        return response

    def _build_dcc_metadata_form(self, dcc_record):
        """Build form data representing the specified metadata update."""

        # Extract data from records.
        related = [ref.format(version=False) for ref in dcc_record.related_to]

        if dcc_record.authors:
            reversed_authors = []
            for author in dcc_record.authors:
                # HACK: put first name at end following a comma. Is there a better way
                # to do this?
                name_pieces = author.name.split()
                extra = " ".join(name_pieces[1:])
                reversed_authors.append(f"{extra}, {name_pieces[0]}")
            authors = "\n".join(reversed_authors)

        if dcc_record.keywords:
            keywords = " ".join(dcc_record.keywords)
        else:
            keywords = None

        fields = [
            (dcc_record.title, "TitleField", "TitleChange"),
            (dcc_record.abstract, "AbstractField", "AbstractChange"),
            (keywords, "KeywordsField", "KeywordsChange"),
            (dcc_record.note, "NotesField", "NotesChange"),
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

    @abc.abstractmethod
    def dcc_record_url(self, dcc_number, xml=True):
        """Build a DCC record URL given the specified DCC number.

        Parameters
        ----------
        dcc_number : :class:`.DCCNumber`
            The DCC record.

        xml : bool, optional
            Whether to make the URL an XML request.

        Returns
        -------
        str
            The URL.
        """
        raise NotImplementedError()

    def _build_dcc_url(self, path=""):
        """Build DCC URL from the specified path."""
        if path:
            path = f"/{path}"

        return f"{self.protocol}://{self.host}{path}"


class DCCAuthenticatedSession(DCCSession, CIECPSession):
    """A SAML/ECP-authenticated DCC HTTP fetcher.

    Parameters
    ----------
    host : str
        The DCC host to use.

    idp : str
        The identity provider host to use.

    Other Parameters
    ----------------
    stream_hook : callable, optional
        Function taking a response type and a :class:`requests.Response` object from a
        GET or POST request, yielding its body content. This can be used to implement
        download progress bars, interactive skipping of downloads, etc.
    """

    def dcc_record_url(self, dcc_number, xml=True):
        pieces = [dcc_number.category, dcc_number.numeric, dcc_number.version_suffix]

        if xml:
            pieces.append("/of=xml")

        return self._build_dcc_url("".join(pieces))

    dcc_record_url.__doc__ = DCCSession.dcc_record_url.__doc__


class DCCUnauthenticatedSession(DCCSession, Session):
    """An unauthenticated DCC HTTP fetcher.

    Parameters
    ----------
    host : str
        The DCC host to use.

    Other Parameters
    ----------------
    stream_hook : callable, optional
        Function taking a response type and a :class:`requests.Response` object from a
        GET or POST request, yielding its body content. This can be used to implement
        download progress bars, interactive skipping of downloads, etc.
    """

    def dcc_record_url(self, dcc_number, xml=True):
        pieces = [
            dcc_number.category,
            dcc_number.numeric,
            dcc_number.version_suffix,
            "/public",
        ]

        if xml:
            pieces.append("/of=xml")

        return self._build_dcc_url("".join(pieces))

    dcc_record_url.__doc__ = DCCSession.dcc_record_url.__doc__
