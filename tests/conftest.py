from functools import partial
from pathlib import Path
import pytest
from dcc.records import DCCNumber, DCCRecord
from dcc.sessions import DCCUnauthenticatedSession

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def xml_response():
    def _(item):
        if isinstance(item, DCCNumber):
            identifier = item.format()
        else:
            raise NotImplementedError

        path = DATA_DIR / f"dcc-number-{identifier}-xml.dat"
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
def mock_session():
    return partial(MockSession, host="dcc.example.org")


class MockSession(DCCUnauthenticatedSession):
    """A mock DCC session object."""

    protocol = "mock"
