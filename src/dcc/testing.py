from functools import singledispatch
from dataclasses import fields
from .records import DCCNumber, DCCAuthor, DCCRecord


def assert_record_meta_matches(record_a, record_b):
    assert fields(record_a) == fields(record_b)

    for field in fields(record_a):
        name = field.name
        assert getattr(record_a, name) == getattr(record_b, name), (
            f"field {repr(record_a)} field {repr(name)} doesn't match that of "
            f"{repr(record_b)}"
        )


@singledispatch
def hash_(item):
    """Hash item."""
    raise NotImplementedError(
        f"Testing hash function not available for {repr(type(item))}."
    )


@hash_.register(DCCNumber)
def _(dcc_number):
    return hash((dcc_number.category, dcc_number.numeric, dcc_number.version))


@hash_.register(DCCAuthor)
def _(dcc_author):
    return hash((dcc_author.name, dcc_author.uid))


@hash_.register(DCCRecord)
def _(dcc_record):
    return hash(
        (
            hash_(dcc_record.dcc_number),
            dcc_record.title,
            tuple(hashall(dcc_record.authors or [])),
            dcc_record.abstract,
            tuple(hashall(dcc_record.keywords or [])),
            dcc_record.note,
            dcc_record.publication_info,
            dcc_record.journal_reference,
            tuple(dcc_record.other_versions or []),
            dcc_record.creation_date,
            dcc_record.contents_revision_date,
            dcc_record.metadata_revision_date,
            tuple(hashall(dcc_record.files or [])),
            tuple(hashall(dcc_record.referenced_by or [])),
            tuple(hashall(dcc_record.related_to or [])),
        )
    )


def hashall(items):
    """Hash all items."""
    return (hash_(item) for item in items)


def assert_orderless_eq(group1, group2):
    assert set(hashall(group1)) == set(hashall(group2))


def orderless_eq(group1, group2):
    try:
        assert set(hashall(group1)) == set(hashall(group2))
    except AssertionError:
        return False
    else:
        return True
