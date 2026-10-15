"""The local-only data registry: absent data is None, other bytes are refused (WP-1325)."""

from __future__ import annotations

import re

import pytest

from tests import local_data


@pytest.fixture
def empty_root(tmp_path, monkeypatch):
    monkeypatch.setenv(local_data.ROOT_ENV, str(tmp_path))
    return tmp_path


def test_every_source_is_a_url_or_a_zip_registered_before_it():
    for files in local_data.DATASETS.values():
        seen: list[str] = []
        for fname, (source, digest) in files.items():
            assert re.fullmatch(r"[0-9a-f]{64}", digest), fname
            assert source.startswith("https://") or (source.endswith(".zip") and source in seen)
            seen.append(fname)


def test_an_absent_dataset_is_none_rather_than_an_error(empty_root):
    assert all(local_data.dataset(name) is None for name in local_data.DATASETS)


def test_a_file_with_other_bytes_is_refused(empty_root):
    name, files = next(iter(local_data.DATASETS.items()))
    where = empty_root / name
    where.mkdir(parents=True)
    (where / next(iter(files))).write_bytes(b"not the registered bytes")
    with pytest.raises(ValueError, match="not the registered file"):
        local_data.dataset(name)
