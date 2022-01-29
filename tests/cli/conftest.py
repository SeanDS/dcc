import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner(archive):
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=archive.archive_dir):
        yield runner
