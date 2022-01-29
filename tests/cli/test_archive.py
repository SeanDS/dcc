"""CLI archive command tests."""

from dcc.__main__ import dcc
from dcc.records import DCCNumber


def test_archive(
    cli_runner, archive, requests_mock, mock_session, xml_response, ref_record
):
    """Archive record."""
    dcc_number = DCCNumber("T1234567")

    # Create a session so we can grab URLs and hosts.
    session = mock_session()

    url = session.dcc_record_url(dcc_number)
    requests_mock.get(url, text=xml_response(dcc_number))

    assert list(archive.records) == []
    result = cli_runner.invoke(
        dcc,
        [
            "archive",
            str(dcc_number),
            "-s",
            str(archive.archive_dir),
            "--public",
            "--host",
            session.host,
        ],
    )
    assert result.exit_code == 0
    assert list(archive.records) == [ref_record(dcc_number)]
