"""CLI view command tests."""

from dcc.__main__ import dcc


def test_view(cli_runner, archive, fetch_ref_record):
    """View record."""
    number = "T1234567"
    record = fetch_ref_record(number)
    archive.archive_revision_metadata(record)

    result = cli_runner.invoke(
        dcc, ["view", number, "-s", str(archive.archive_dir), "--ignore-version"]
    )
    assert result.exit_code == 0
    assert number in result.stdout and len(result.stdout.splitlines()) == 12
