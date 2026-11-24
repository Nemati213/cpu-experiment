from importlib import import_module

import pytest


@pytest.mark.parametrize("name", ["isa", "translator", "machine"])
def test_module_import(name: str) -> None:
    assert import_module(name).__name__ == name
