from functools import partial
from pathlib import Path
import pytest
from dcc.records import DCCArchive, DCCNumber, DCCRecord
from dcc.sessions import DCCUnauthenticatedSession

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def xml_response():
    def _(item):
        if isinstance(item, DCCNumber):
            identifier = item.format()
        else:
            raise NotImplementedError

        path = DATA_DIR / f"dcc-number-{identifier}.xml"
        with path.open("r") as fobj:
            return fobj.read()

    return _


@pytest.fixture
def ref_record():
    def _(dcc_number, **kwargs):
        identifier = dcc_number.format()
        path = DATA_DIR / f"dcc-number-{identifier}-meta.toml"
        return DCCRecord.read(path)

    return _


@pytest.fixture
def archive(tmp_path):
    return DCCArchive(tmp_path)


@pytest.fixture
def mock_session():
    class MockSession(DCCUnauthenticatedSession):
        """A mock DCC session object."""

        protocol = "mock"

    return partial(MockSession, host="dcc.example.org")
