"""Communication with the DCC."""

import logging
from ciecplib import Session as CIECPSession
from .exceptions import FileTooLargeError, DryRun

LOGGER = logging.getLogger(__name__)


class DCCSession(CIECPSession):
    """A SAML/ECP-authenticated DCC HTTP fetcher.

    Parameters
    ----------
    host : str
        The DCC host to use.

    idp : str
        The identity provider host to use.

    max_file_size : int, optional
        Maximum file size to download, in bytes. Defaults to None, which means no limit.

    simulate : bool, optional
        Instead of making POST requests to the remote DCC host, raise a :class:`.DryRun`
        exception.

    download_progress_hook : iterable, optional
        Function taking object, iterable (the streamed download chunks) and total length
        arguments, yielding each provided chunk. This can be used to display a progress
        bar. Note: the hook is only called if the response provides a Content-Length
        header.
    """

    # Transport protocol.
    protocol = "https"

    def __init__(
        self,
        host,
        idp,
        max_file_size=None,
        simulate=False,
        download_progress_hook=None,
        **kwargs,
    ):
        super().__init__(idp=idp, **kwargs)

        self.host = host
        self.max_file_size = max_file_size
        self.simulate = simulate
        self.download_progress_hook = download_progress_hook

        LOGGER.debug(f"Created session at DCC host {host} using IDP {idp}.")

    def post(self, *args, **kwargs):
        if self.simulate:
            LOGGER.info(f"Simulating POST: {args}, {kwargs}")
            raise DryRun()

        return super().post(*args, **kwargs)

    post.__doc__ = CIECPSession.post.__doc__

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
        response = self.get(self.dcc_record_url(dcc_number))
        response.raise_for_status()
        return response

    def fetch_file_contents(self, dcc_file):
        """Fetch the remote contents of the specified file.

        Parameters
        ----------
        dcc_file : :class:`.DCCFile`
            The DCC file to fetch.

        Returns
        -------
        :class:`requests.Response`
            The HTTP response.
        """
        response = self.get(dcc_file.url, stream=True)
        response.raise_for_status()
        content_length = response.headers.get("content-length")

        if content_length:
            content_length = int(content_length)
            LOGGER.debug(f"Content length: {content_length}")
            if self.max_file_size is not None and content_length > self.max_file_size:
                raise FileTooLargeError(dcc_file, content_length, self.max_file_size)

            if self.download_progress_hook is not None:
                return self.download_progress_hook(dcc_file, response, content_length)

        return response

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

        data["DocumentsField"] = dcc_record.dcc_number.string_repr(version=False)
        data["DocumentChange"] = "Change Latest Version"

        # Submit form data.
        response = self.post(dcc_update_metadata_url, data)
        response.raise_for_status()
        return response

    def _build_dcc_metadata_form(self, dcc_record):
        """Build form data representing the specified metadata update."""

        # Extract data from records.
        related = [ref.string_repr(version=False) for ref in dcc_record.related_to]

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
        pieces = [dcc_number.category, dcc_number.numeric, dcc_number.version_suffix]
        if xml:
            pieces.append("/of=xml")
        return self._build_dcc_url("".join(pieces))

    def _build_dcc_url(self, path=""):
        """Build DCC URL from the specified path."""
        if path:
            path = f"/{path}"

        return f"{self.protocol}://{self.host}{path}"

    def _build_dcc_author_url(self, author):
        """Build DCC author page URL from the specified author.

        :param author: author to download
        """

        return self._build_dcc_url(
            f"cgi-bin/private/DocDB/ListBy?authorid={author.uid}"
        )
