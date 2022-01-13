"""Utilities."""

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def opened_file(fobj, mode):
    """Get an open file regardless of whether a string or an already open file is
    passed.

    Parameters
    ----------
    fobj : str, :class:`pathlib.Path`, or file-like
        The path or file object to ensure is open. If `fobj` is an already open file
        object, its mode is checked to be correct but is otherwise returned as-is. If
        `fobj` is a string, it is opened with the specified `mode` and yielded, then
        closed once the wrapped context exits. Note that passed open file objects are
        *not* closed.

    mode : str
        The mode to ensure `fobj` is opened with.

    Yields
    ------
    :class:`io.FileIO`
        The open file with the specified `mode`.

    Raises
    ------
    ValueError
        If `fobj` is not a string nor open file, or if `fobj` is open but with a
        different `mode`.
    """
    close = False

    if isinstance(fobj, (str, Path)):
        fobj = open(fobj, mode)
        close = True  # Close the file we just opened once we're done.
    else:
        try:
            # Ensure mode agrees.
            if fobj.mode != mode:
                raise ValueError(
                    f"Unexpected mode for '{fobj.name}' (expected '{mode}', got "
                    f"'{fobj.mode}')"
                )
        except AttributeError:
            raise ValueError(f"'{fobj}' is not an open file or path.")

    try:
        yield fobj
    finally:
        if close:
            fobj.close()
