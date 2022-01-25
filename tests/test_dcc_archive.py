"""Test sessions."""

from dcc.records import DCCArchive, DCCRecord, DCCNumber
from dcc.testing import assert_orderless_eq


def test_documents(tmp_path):
    """Test document listing."""
    archive = DCCArchive(tmp_path)

    assert not list(archive.documents)

    # Add a record.
    archive.archive_revision_metadata(
        DCCRecord(dcc_number="M1234567-v2", title="A title.")
    )
    assert_orderless_eq(archive.documents, [DCCNumber("M1234567")])

    # Add another record.
    archive.archive_revision_metadata(
        DCCRecord(dcc_number="T7654321-v3", title="A title.")
    )
    twonumbers = [DCCNumber("M1234567"), DCCNumber("T7654321")]
    assert_orderless_eq(archive.documents, twonumbers)

    # Add a non-archive file to the document directory. It should be ignored.
    ignore_file = tmp_path / "ignore.txt"
    ignore_file.touch()
    assert ignore_file.is_file()
    assert_orderless_eq(archive.documents, twonumbers)

    # Add a non-archive directory to the document directory. It should be ignored.
    ignore_dir = tmp_path / "ignore-dir"
    ignore_dir.mkdir()
    assert ignore_dir.is_dir()
    assert_orderless_eq(archive.documents, twonumbers)

    # Add a revision of the same document. This should not appear as a separate
    # document.
    archive.archive_revision_metadata(
        DCCRecord(dcc_number="T7654321-v4", title="A title.")
    )
    assert_orderless_eq(archive.documents, twonumbers)


def test_records(tmp_path):
    """Test record listing."""
    archive = DCCArchive(tmp_path)

    assert not list(archive.records)

    # Add a record.
    record1 = DCCRecord(dcc_number="M1234567-v2", title="A title.")
    archive.archive_revision_metadata(record1)
    assert_orderless_eq(archive.records, [record1])

    # Add another record.
    record2 = DCCRecord(dcc_number="T7654321-v3", title="A title.")
    archive.archive_revision_metadata(record2)
    tworecords = [record1, record2]
    assert_orderless_eq(archive.records, tworecords)

    # Add a non-archive file to the record directory. It should be ignored.
    ignore_file = archive.revision_dir(record1.dcc_number) / "ignore.txt"
    ignore_file.touch()
    assert ignore_file.is_file()
    assert_orderless_eq(archive.records, tworecords)

    # Add a non-archive directory to the record directory. It should be ignored.
    ignore_dir = archive.revision_dir(record1.dcc_number) / "ignore-dir"
    ignore_dir.mkdir()
    assert ignore_dir.is_dir()
    assert_orderless_eq(archive.records, tworecords)

    # Add a revision of the same document. This should appear as a separate record.
    record3 = DCCRecord(dcc_number="T7654321-v4", title="A title.")
    archive.archive_revision_metadata(record3)
    assert_orderless_eq(archive.records, [record1, record2, record3])
