import os
import sys
from pathlib import Path
import pytest

# Add the test root directory to the path so test scripts can import the testutils
# package directly.
sys.path.append(str(Path(__file__).parent))

# Register testing module assertion error rewriting.
# NOTE: this needs to happen early in the import chain.
pytest.register_assert_rewrite("dcc.testing")

from dcc.records import DCCArchive, DCCNumber, DCCRecord
from dcc.sessions import DCCUnauthenticatedSession, DCCAuthenticatedSession

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def fetch_ref_record():
    def _(dcc_number, **kwargs):
        if isinstance(dcc_number, DCCNumber):
            dcc_number = dcc_number.format()

        path = DATA_DIR / f"dcc-number-{dcc_number}-meta.toml"
        return DCCRecord.read(path)

    return _


@pytest.fixture(scope="session")
def ref_records(fetch_ref_record):
    records = {}

    for record in DATA_DIR.glob("dcc-number-*-meta.toml"):
        dcc_number = record.name[len("dcc-number-"):-len("-meta.toml")]
        records[dcc_number] = fetch_ref_record(dcc_number)

    return records


@pytest.fixture
def archive(tmp_path):
    return DCCArchive(tmp_path)


# Ideally this would be session scoped, but requests_mock doesn't allow it.
@pytest.fixture
def mock_session(requests_mock, xml_response, ref_records):
    with DCCUnauthenticatedSession(host="dcc.example.org") as session:
        # Register the endpoints and responses in the data directory.
        for dcc_number, dcc_record in ref_records.items():
            xml = xml_response(dcc_record.dcc_number)
            # Use the exact number specified in the filename in case it's versionless.
            url = session.dcc_record_url(DCCNumber(dcc_number))
            requests_mock.get(url, text=xml)

        yield session


@pytest.fixture(scope="session")
def dcc_test_session():
    kwargs = {
        "host": os.environ["DCC_TEST_HOST"],
        "idp": os.environ["DCC_TEST_IDP_HOST"],
        "username": os.environ["DCC_TEST_USERNAME"],
        "password": os.environ["DCC_TEST_PASSWORD"]
    }

    with DCCAuthenticatedSession(**kwargs) as session:
        yield session
