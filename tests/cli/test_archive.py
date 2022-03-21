"""CLI archive command tests."""

from dcc.__main__ import dcc
from dcc.records import DCCNumber


def test_archive(
    cli_runner, archive, requests_mock, mock_session, xml_response, fetch_ref_record
):
    """Archive record."""
    dcc_number = DCCNumber("T1234567")

    url = mock_session.dcc_record_url(dcc_number)
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
            mock_session.host,
        ],
    )
    assert result.exit_code == 0
    assert list(archive.records) == [fetch_ref_record(dcc_number)]
