"""CLI list command tests."""

from dcc.__main__ import dcc


def test_list_empty(cli_runner):
    """List with empty archive."""
    # Without archive path, list is empty.
    result = cli_runner.invoke(dcc, ["list"])
    assert result.exit_code == 0
    assert not result.stdout


def test_list_one_record(cli_runner, archive, ref_record):
    """List with archive with one record."""
    record = ref_record("T1234567")
    archive.archive_revision_metadata(record)

    # With archive path, should have 1 record.
    result = cli_runner.invoke(dcc, ["list", "-s", str(archive.archive_dir)])
    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["T1234567-v2: This is the title."]

    # With the --full flag, the output should span many lines.
    result = cli_runner.invoke(dcc, ["list", "-s", str(archive.archive_dir), "--full"])
    assert result.exit_code == 0
    assert len(result.stdout.splitlines()) == 13
