"""Test DCC archive."""

import pytest
from dcc.records import DCCRecord, DCCNumber
from dcc.testing import assert_orderless_eq, assert_record_meta_matches


def test_documents(archive):
    """Test document listing."""
    assert_orderless_eq(archive.documents, [])

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
    ignore_file = archive.archive_dir / "ignore.txt"
    ignore_file.touch()
    assert ignore_file.is_file()
    assert_orderless_eq(archive.documents, twonumbers)

    # Add a non-archive directory to the document directory. It should be ignored.
    ignore_dir = archive.archive_dir / "ignore-dir"
    ignore_dir.mkdir()
    assert ignore_dir.is_dir()
    assert_orderless_eq(archive.documents, twonumbers)

    # Add a revision of the same document. This should not appear as a separate
    # document.
    archive.archive_revision_metadata(
        DCCRecord(dcc_number="T7654321-v4", title="A title.")
    )
    assert_orderless_eq(archive.documents, twonumbers)


def test_records(archive):
    """Test record listing."""
    assert_orderless_eq(archive.records, [])

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


def test_latest_revisions(archive):
    """Test latest revisions listing."""
    assert_orderless_eq(archive.latest_revisions, [])

    # Add a record.
    record1 = DCCRecord(dcc_number="M1234567-v2", title="A title.")
    archive.archive_revision_metadata(record1)
    assert_orderless_eq(archive.latest_revisions, [record1])

    # Add another record.
    record2 = DCCRecord(dcc_number="T7654321-v3", title="A title.")
    archive.archive_revision_metadata(record2)
    assert_orderless_eq(archive.latest_revisions, [record1, record2])

    # Add a revision of the same document.
    record3 = DCCRecord(dcc_number="T7654321-v4", title="A title.")
    archive.archive_revision_metadata(record3)
    assert_orderless_eq(archive.latest_revisions, [record1, record3])


def test_fetch_record(requests_mock, mock_session, xml_response, ref_record, archive):
    """Test fetching of a DCC record not in the current archive."""
    dcc_number = DCCNumber("T1234567")
    xml = xml_response(dcc_number)
    reference = ref_record(dcc_number)

    assert_orderless_eq(archive.records, [])

    with mock_session() as session:
        url = session.dcc_record_url(dcc_number)
        requests_mock.get(url, text=xml)
        assert_record_meta_matches(
            archive.fetch_record(dcc_number, session=session), reference
        )

    assert_orderless_eq(archive.records, [reference])


@pytest.mark.parametrize("ignore_version", (False, True))
def test_fetch_existing_record__with_versioned_number(
    requests_mock, mock_session, ref_record, archive, ignore_version
):
    """Test fetching of a record already in the archive using a versioned DCC number.

    As a version is specified in the DCC number, it is found in the archive and returned
    without a connection to the remote DCC.
    """
    dcc_number = DCCNumber("T1234567-v2")
    reference = ref_record(dcc_number)

    assert_orderless_eq(archive.records, [])
    archive.archive_revision_metadata(reference)
    assert_orderless_eq(archive.records, [reference])

    with mock_session() as session:
        assert_record_meta_matches(
            archive.fetch_record(
                dcc_number, ignore_version=ignore_version, session=session
            ),
            reference,
        )

    assert_orderless_eq(archive.records, [reference])


@pytest.mark.parametrize("ignore_version", (False, True))
@pytest.mark.parametrize("overwrite", (False, True))
def test_fetch_existing_record__with_versioned_number__force(
    requests_mock,
    mock_session,
    xml_response,
    ref_record,
    archive,
    ignore_version,
    overwrite,
):
    """Test fetching of a record already in the archive using a versioned DCC number,
    where the fetched record is fetched anyway.

    The reference record is changed before being added to the archive so that we can
    detect whether an overwrite has occurred.
    """
    dcc_number = DCCNumber("T1234567-v2")
    xml = xml_response(dcc_number)
    reference = ref_record(dcc_number)

    # Change the referenced record.
    reference.title = "__changed__"

    assert_orderless_eq(archive.records, [])
    archive.archive_revision_metadata(reference)
    assert_orderless_eq(archive.records, [reference])

    with mock_session() as session:
        url = session.dcc_record_url(dcc_number)
        requests_mock.get(url, text=xml)
        fetched = archive.fetch_record(
            dcc_number,
            ignore_version=ignore_version,
            overwrite=overwrite,
            session=session,
        )

    if overwrite:
        assert_orderless_eq(archive.records, [fetched])
    else:
        assert_orderless_eq(archive.records, [reference])


def test_fetch_existing_record__with_nonversioned_number(
    requests_mock, mock_session, xml_response, ref_record, archive
):
    """Test fetching of a record already in the archive using a versionless DCC number.

    As no version is specified in the DCC number, a connection is made to the remote DCC
    to get the latest record. The retrieved record should be identical to the existing
    one, so it is not overwritten.
    """
    dcc_number = DCCNumber("T1234567")
    xml = xml_response(dcc_number)
    reference = ref_record(dcc_number)

    assert_orderless_eq(archive.records, [])
    archive.archive_revision_metadata(reference)
    assert_orderless_eq(archive.records, [reference])

    with mock_session() as session:
        url = session.dcc_record_url(dcc_number)
        requests_mock.get(url, text=xml)
        assert_record_meta_matches(
            archive.fetch_record(dcc_number, ignore_version=False, session=session),
            reference,
        )

    assert_orderless_eq(archive.records, [reference])


def test_fetch_existing_record__with_nonversioned_number__ignore_version(
    mock_session, ref_record, archive
):
    """Test fetching of a record already in the archive using a versionless DCC number,
    when version is set to be ignored.

    No connection to the remote DCC should be made.
    """
    dcc_number = DCCNumber("T1234567")
    reference = ref_record(dcc_number)

    assert_orderless_eq(archive.records, [])
    archive.archive_revision_metadata(reference)
    assert_orderless_eq(archive.records, [reference])

    with mock_session() as session:
        assert_record_meta_matches(
            archive.fetch_record(dcc_number, ignore_version=True, session=session),
            reference,
        )

    assert_orderless_eq(archive.records, [reference])
