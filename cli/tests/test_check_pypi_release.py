import hashlib
from pathlib import Path

import pytest

from tools import check_pypi_release


def test_only_exact_pypi_distributions_can_be_resumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wheel = "example-1.0.0-py3-none-any.whl"
    sdist = "example-1.0.0.tar.gz"
    (tmp_path / wheel).write_bytes(b"wheel")
    (tmp_path / sdist).write_bytes(b"sdist")
    published = {wheel: hashlib.sha256(b"wheel").hexdigest()}
    monkeypatch.setattr(
        check_pypi_release, "published_hashes", lambda package, version: published
    )
    monkeypatch.setattr(check_pypi_release.time, "sleep", lambda seconds: None)

    check_pypi_release.check(tmp_path, "example", "1.0.0", complete=False)
    with pytest.raises(ValueError, match="did not expose every"):
        check_pypi_release.check(tmp_path, "example", "1.0.0", complete=True)
    published[sdist] = hashlib.sha256(b"sdist").hexdigest()
    check_pypi_release.check(tmp_path, "example", "1.0.0", complete=True)

    published[wheel] = hashlib.sha256(b"different").hexdigest()
    with pytest.raises(ValueError, match="contains different distributions"):
        check_pypi_release.check(tmp_path, "example", "1.0.0", complete=False)
