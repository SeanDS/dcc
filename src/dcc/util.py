"""Utilities."""

from contextlib import contextmanager
from pathlib import Path


# Allowed opened file mode pairs.
_MODE_MAP = (
    ("r", "r"),
    ("r", "+"),
    ("w", "w"),
    ("w", "+"),
    ("x", "x"),
    ("a", "a"),
    ("+", "+"),
    ("+", "r"),
    ("+", "w"),
)


def change_exc_msg(exc, new_msg):
    """Change exception message."""
    exc.args = (new_msg,) + exc.args[1:]


def remove_none(container):
    """Remove None values from the specified container.

    Adapted from https://stackoverflow.com/a/20558778/2251982.
    """
    if isinstance(container, (list, tuple, set)):
        return type(container)(remove_none(x) for x in container if x is not None)
    elif isinstance(container, dict):
        return type(container)(
            (k, remove_none(v)) for k, v in container.items() if v is not None
        )
    return container


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
            if not any(lm in mode and rm in fobj.mode for lm, rm in _MODE_MAP):
                raise ValueError(
                    f"Unexpected mode for {repr(fobj.name)} (expected mode compatible "
                    f"with {repr(mode)}, got {repr(fobj.mode)})."
                )
        except AttributeError:
            raise ValueError(f"{repr(fobj)} is not an open file or path.")

    try:
        yield fobj
    finally:
        if close:
            fobj.close()


def human_file_size(length):
    """Convert length in bytes to a human file size.

    Parameters
    ----------
    length : :class:`int`
        The file size in bytes.

    Returns
    -------
    :class:`int`
        The scaled file size.

    :class:`str`
        The unit, e.g. "B" (bytes) or "GB" (gigabytes).
    """
    if length >= 1024 * 1024 * 1024:
        value = length / (1024 * 1024 * 1024)
        unit = "GB"
    elif length >= 1024 * 1024:
        value = length / (1024 * 1024)
        unit = "MB"
    elif length >= 1024:
        value = length / 1024
        unit = "kB"
    else:
        value = length
        unit = "B"

    return value, unit
