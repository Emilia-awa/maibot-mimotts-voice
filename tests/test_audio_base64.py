"""Tests for the audio base64 normalizer in tts_service.py."""

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LENGTHS = list(range(1, 13))
PREFIXES = ["data:audio/wav;base64,", "data:audio/mpeg;base64,", "data:audio/aac;base64,"]


def _load_tts_service():
    name = "_req_tts_service_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tts_service.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


normalize = _load_tts_service()._normalize_audio_base64


def _raw(length: int) -> bytes:
    # Deterministic, non-repeating bytes so padding edge cases are stable.
    return bytes((i * 37 + 11) % 256 for i in range(length))


def _strip_padding(value: str) -> str:
    return value.rstrip("=")


@pytest.mark.parametrize("length", LENGTHS)
def test_padded_input_decodes_to_original(length):
    raw = _raw(length)
    encoded = base64.b64encode(raw).decode("ascii")
    assert base64.b64decode(normalize(encoded)) == raw


@pytest.mark.parametrize("length", LENGTHS)
def test_unpadded_input_decodes_to_original(length):
    raw = _raw(length)
    encoded = _strip_padding(base64.b64encode(raw).decode("ascii"))
    assert base64.b64decode(normalize(encoded)) == raw


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("length", LENGTHS)
def test_data_url_prefix_is_stripped_before_padding(prefix, length):
    raw = _raw(length)
    encoded = _strip_padding(base64.b64encode(raw).decode("ascii"))
    result = normalize(prefix + encoded)
    assert "data:" not in result
    assert "base64," not in result
    assert base64.b64decode(result) == raw


def test_normalization_is_idempotent_for_all_samples():
    samples = []
    for length in LENGTHS:
        raw = _raw(length)
        padded = base64.b64encode(raw).decode("ascii")
        unpadded = _strip_padding(padded)
        samples.extend([padded, unpadded])
        for prefix in PREFIXES:
            samples.extend([prefix + padded, prefix + unpadded])

    for sample in samples:
        once = normalize(sample)
        assert normalize(once) == once, sample


@pytest.mark.parametrize(
    "value",
    ["YWJj\nZGU", "  YWJj ZGU  ", "YWJj\r\n\tZGU"],
)
def test_whitespace_is_removed_before_padding(value):
    assert normalize(value) == "YWJjZGU="


@pytest.mark.parametrize("value", ["", "   ", "\n\t\r ", None])
def test_empty_values_normalize_to_empty_string(value):
    assert normalize(value) == ""


@pytest.mark.parametrize(
    "value",
    [
        "YWJjZGU",
        "YWJjZA",
        "YWJjZGVm",
        "YWJjZGU=",
        "data:audio/wav;base64,YWJjZGU",
        "data:audio/mpeg;base64,YWJjZGVm",
        "data:audio/aac;base64,YWJjZA",
        "  YWJj ZGU  ",
    ],
)
def test_output_never_contains_data_url_artifacts(value):
    result = normalize(value)
    assert "data:" not in result
    assert "base64," not in result


def test_last_base64_marker_wins():
    assert normalize("junk,base64,YWJjZGVm") == "YWJjZGVm"


def test_already_padded_value_is_unchanged():
    assert normalize("YWJjZGU=") == "YWJjZGU="
