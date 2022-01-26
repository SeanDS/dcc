"""Test DCC records."""

from datetime import datetime
import pytest
from dcc.records import DCCNumber, DCCRecord, DCCAuthor, DCCJournalRef, DCCFile
from dcc.testing import assert_record_meta_matches


@pytest.mark.parametrize("dcc_number", (DCCNumber("T1234567"),))
def test_fetch(requests_mock, mock_session, xml_response, ref_record, dcc_number):
    """Test fetching record from (mock) DCC."""
    xml = xml_response(dcc_number)
    reference = ref_record(dcc_number)

    with mock_session() as session:
        url = session.dcc_record_url(dcc_number)
        requests_mock.get(url, text=xml)
        fetched = DCCRecord.fetch(dcc_number, session=session)

    assert_record_meta_matches(fetched, reference)


def test_write_read(tmp_path):
    """Test serialisation and deserialisation preserves record metadata."""
    record = DCCRecord(
        dcc_number="M1234567-v2",
        title="A title.",
        authors=[DCCAuthor("John Doe"), DCCAuthor("Jane Doe")],
        abstract="An abstract.",
        keywords=["Keyword 1", "Keyword 2"],
        note="A note.",
        publication_info="Publication info.",
        journal_reference=DCCJournalRef(
            "A Journal",
            3,
            "123--126",
            "Journal 3, 123--126",
            url="https://example.org/journal/3/",
        ),
        other_versions=[0, 1],
        creation_date=datetime(2022, 1, 25, 16, 27, 30),
        contents_revision_date=datetime(2022, 1, 25, 16, 27, 31),
        metadata_revision_date=datetime(2022, 1, 25, 16, 27, 32),
        files=[
            DCCFile("A File.", "file_1.pdf", url="mock://dcc.example.org/file_1.pdf"),
            DCCFile(
                "Another File.", "file_1.pdf", url="mock://dcc.example.org/file_2.pdf"
            ),
        ],
        referenced_by=[DCCNumber("T1234567")],
        related_to=[DCCNumber("T7654321")],
    )

    path = tmp_path / "record.toml"
    record.write(path)
    loaded = DCCRecord.read(path)
    assert_record_meta_matches(record, loaded)
