"""
Tests for READER_DIRECTION config parsing — one bridge instance = one physical
reader, configured as the "in" or "out" side of a barrier/door.
"""
import importlib
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from bridge_agent import config as _config


def _reload_with(value):
    if value is None:
        os.environ.pop("READER_DIRECTION", None)
    else:
        os.environ["READER_DIRECTION"] = value
    importlib.reload(_config)
    return _config.READER_DIRECTION


class TestReaderDirection:
    def test_defaults_to_in_when_unset(self):
        assert _reload_with(None) == "in"

    def test_accepts_out(self):
        assert _reload_with("out") == "out"

    def test_accepts_in_explicitly(self):
        assert _reload_with("in") == "in"

    def test_is_case_insensitive(self):
        assert _reload_with("OUT") == "out"

    def test_invalid_value_falls_back_to_in(self):
        assert _reload_with("sideways") == "in"

    def test_trims_whitespace(self):
        assert _reload_with("  out  ") == "out"

    def teardown_method(self):
        os.environ.pop("READER_DIRECTION", None)
        importlib.reload(_config)
