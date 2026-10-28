import pytest

from fpl_showcase.errors import ShowcaseError
from fpl_showcase.immutable_io import install_json, read_object


def inside(_path):
    return None


def test_install_json_creates_immutable_slot(tmp_path):
    path = tmp_path / "result.json"

    created = install_json(
        path,
        {"result": 42},
        inside=inside,
        error=ShowcaseError,
    )

    assert created is True
    assert read_object(
        path,
        error=ShowcaseError,
    ) == {"result": 42}


def test_identical_second_install_is_idempotent(tmp_path):
    path = tmp_path / "result.json"

    assert install_json(
        path,
        {"result": 42},
        inside=inside,
        error=ShowcaseError,
    )

    assert install_json(
        path,
        {"result": 42},
        inside=inside,
        error=ShowcaseError,
    ) is False


def test_different_content_cannot_replace_slot(tmp_path):
    path = tmp_path / "result.json"

    install_json(
        path,
        {"result": 42},
        inside=inside,
        error=ShowcaseError,
    )

    with pytest.raises(
        ShowcaseError,
        match="different content",
    ):
        install_json(
            path,
            {"result": 99},
            inside=inside,
            error=ShowcaseError,
        )


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text(
        '{"value":1,"value":2}',
        encoding="utf-8",
    )

    with pytest.raises(
        ShowcaseError,
        match="duplicate JSON key",
    ):
        read_object(
            path,
            error=ShowcaseError,
        )
