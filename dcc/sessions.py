"""Communication with the DCC."""

import abc
import logging
from tempfile import mkdtemp
from pathlib import Path
from ciecplib import Session as CIECPSession
from .exceptions import NoVersionError, DryRun

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

    def dcc_record_url(self, dcc_number, xml=True):
        """Builds a DCC record base URL given the specified DCC number.

        :param dcc_number: number of DCC record to download
        :param xml: whether to append the XML request string
        """
        pieces = [dcc_number.category, dcc_number.numeric, dcc_number.version_suffix]
        if xml:
            pieces.append("/of=xml")
        return self._build_dcc_url("".join(pieces))

    def fetch_record_page(self, dcc_number):
        """Fetches the DCC record page specified by the provided number.

        :param dcc_number: DCC number to fetch record for
        """
        response = self.get(self.dcc_record_url(dcc_number))
        response.raise_for_status()
        return response

    def fetch_file_contents(self, dcc_file, stream=True):
        """Fetch the file associated with the specified file.

        :param dcc_file: file to stream data for
        """
        response = self.get(dcc_file.url, stream=stream)
        response.raise_for_status()
        return response

    def update_record_metadata(self, dcc_record):
        """Update metadata for the DCC record specified by the provided number.

        The version (if any) of the provided DCC number is ignored. Only the latest
        version of the record is updated.

        Returns the response of the server to the update request.

        :param dcc_record: the DCC record to update
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
        authors = [author.name for author in dcc_record.authors]

        fields = [
            (dcc_record.title, "TitleField", "TitleChange"),
            (dcc_record.abstract, "AbstractField", "AbstractChange"),
            (dcc_record.keywords, "KeywordsField", "KeywordsChange"),
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


class DCCSession(CIECPSession, DCCHTTPFetcher):
    """A SAML/ECP-authenticated DCC HTTP fetcher."""

    def __init__(
        self, host, idp, archive_dir=None, overwrite=False, simulate=False, **kwargs
    ):
        # Workaround for ciecplib #86.
        DCCHTTPFetcher.__init__(self, host=host)
        CIECPSession.__init__(self, idp=idp, **kwargs)

        if archive_dir is None:
            # Use a temporary directory.
            archive_dir = mkdtemp(prefix="dcc-")

        self.archive_dir = Path(archive_dir)
        self.overwrite = overwrite
        self.simulate = simulate

        LOGGER.debug(
            f"Created session at DCC host {host} using IDP {idp} using cache at "
            f"{self.archive_dir.resolve()}"
        )

    def document_archive_dir(self, dcc_number):
        # We require an archive directory and version.
        if not dcc_number.has_version():
            raise NoVersionError()

        return self.archive_dir / dcc_number.string_repr(version=False)

    def record_archive_dir(self, dcc_number):
        document_path = self.document_archive_dir(dcc_number)
        return document_path / dcc_number.string_repr(version=True)

    def file_archive_path(self, dcc_record, dcc_file):
        return self.record_archive_dir(dcc_record.dcc_number) / dcc_file.filename

    def post(self, *args, **kwargs):
        if self.simulate:
            LOGGER.info(f"Simulating POST: {args}, {kwargs}")
            raise DryRun()

        return super().post(*args, **kwargs)
