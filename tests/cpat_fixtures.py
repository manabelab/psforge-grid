"""Locate CPAT-derived test data that is not distributed with this repository.

The IEEJ WEST10 model in CPAT ``.pop`` format and the model system from the
CPAT manual originate from CPATFree (CRIEPI). They are not redistributed here,
so the tests that need them are skipped unless the files are available locally.

Lookup order:

1. The directory named by the ``PSFORGE_CPAT_DATA`` environment variable
2. ``tests/fixtures/cpat_local/`` (git-ignored)

Expected files (see ``tests/fixtures/README.md``):

- ``WEST10peak.pop``: copy of ``CPATFree/Data/IEEJ標準モデル/WEST10peak.pop``
  from your own CPATFree installation
- ``cpat_model11.dyna``: the 10-node model system from the CPAT manual,
  written in dyna card format
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

CPAT_DATA_ENV = "PSFORGE_CPAT_DATA"
LOCAL_CPAT_DIR = Path(__file__).parent / "fixtures" / "cpat_local"


def cpat_data_dir() -> Path:
    """Return the directory that holds locally supplied CPAT test data."""
    env = os.environ.get(CPAT_DATA_ENV)
    return Path(env).expanduser() if env else LOCAL_CPAT_DIR


WEST10_POP = cpat_data_dir() / "WEST10peak.pop"
CPAT_MODEL11_DYNA = cpat_data_dir() / "cpat_model11.dyna"

_HINT = f"set {CPAT_DATA_ENV} or place it in tests/fixtures/cpat_local/"

requires_west10 = pytest.mark.skipif(
    not WEST10_POP.is_file(),
    reason=f"WEST10peak.pop is not distributed ({_HINT})",
)
requires_model11 = pytest.mark.skipif(
    not CPAT_MODEL11_DYNA.is_file(),
    reason=f"cpat_model11.dyna is not distributed ({_HINT})",
)


def skip_without_west10() -> None:
    """Skip the calling test or fixture when WEST10peak.pop is unavailable."""
    if not WEST10_POP.is_file():
        pytest.skip(f"WEST10peak.pop is not distributed ({_HINT})")


def skip_without_model11() -> None:
    """Skip the calling test or fixture when cpat_model11.dyna is unavailable."""
    if not CPAT_MODEL11_DYNA.is_file():
        pytest.skip(f"cpat_model11.dyna is not distributed ({_HINT})")
