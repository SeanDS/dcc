from dataclasses import fields


def assert_record_meta_matches(record_a, record_b):
    assert fields(record_a) == fields(record_b)

    for field in fields(record_a):
        name = field.name
        assert getattr(record_a, name) == getattr(record_b, name), (
            f"field {repr(record_a)} field {repr(name)} doesn't match that of "
            f"{repr(record_b)}"
        )
