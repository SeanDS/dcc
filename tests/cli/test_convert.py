"""CLI convert command tests."""

import pytest
from dcc.__main__ import dcc


convert_codes = pytest.mark.parametrize(
    "contents,codes",
    (
        # Empty.
        ("", []),
        # Textual.
        ("T1234567", ["T1234567"]),
        ("the code is 'T1234567'\n", ["T1234567"]),
        ("the code is 'T1234567-vx'\n", ["T1234567"]),
        ("the code is 'T1234567-v1'\n", ["T1234567-v1"]),
        (
            "codes: T1234567-v1\nD7654321  \n  G1234567-x0",
            ["T1234567-v1", "D7654321", "G1234567-x0"],
        ),
        # HTML.
        pytest.param(
            """
            <html>
                <body>
                    <p>codes:</p>
                    <ul>
                        <li>T1234567-v1</li>
                        <li>D7654321  </li>
                        <li>G1234567-x0</li>
                    </ul>
                </body>
            </html>
            """,
            ["T1234567-v1", "D7654321", "G1234567-x0"],
            id="html",
        ),
    ),
)


@convert_codes
def test_convert_file(tmp_path, cli_runner, contents, codes):
    """Convert from file."""
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    dst.touch()

    with src.open("w") as fobj:
        fobj.write(contents)

    result = cli_runner.invoke(dcc, ["convert", str(src), str(dst)])
    assert result.exit_code == 0
    assert not result.stdout

    with dst.open("r") as fobj:
        assert set(fobj.read().splitlines()) == set(codes)


@convert_codes
def test_convert_url(tmp_path, requests_mock, cli_runner, contents, codes):
    """Convert from file."""
    src = "http://example.org/codes.html"
    requests_mock.get(src, text=contents)
    dst = tmp_path / "dst.txt"
    dst.touch()

    # Use --public to avoid triggering authentication check.
    result = cli_runner.invoke(dcc, ["convert", str(src), str(dst), "--public"])
    assert result.exit_code == 0
    assert not result.stdout

    with dst.open("r") as fobj:
        assert set(fobj.read().splitlines()) == set(codes)
