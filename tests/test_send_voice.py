"""Tests for _send_voice and the voice_clone_tts send-result reporting."""

import asyncio
import base64
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = b"hello voice bytes"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_sdk_stubs():
    """Install minimal stand-ins for maibot_sdk so plugin.py can be imported."""
    if "maibot_sdk" in sys.modules:
        return

    sdk = types.ModuleType("maibot_sdk")

    def _passthrough_decorator(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def _field(default=None, *, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    class MaiBotPlugin:
        def __init__(self):
            self.ctx = None

    class PluginConfigBase:
        pass

    sdk.API = _passthrough_decorator
    sdk.Tool = _passthrough_decorator
    sdk.Field = _field
    sdk.MaiBotPlugin = MaiBotPlugin
    sdk.PluginConfigBase = PluginConfigBase
    sdk.CONFIG_RELOAD_SCOPE_SELF = "self"

    types_mod = types.ModuleType("maibot_sdk.types")

    class ActivationType:
        ALWAYS = "always"

    class ToolParamType:
        STRING = "string"

    class ToolParameterInfo:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    types_mod.ActivationType = ActivationType
    types_mod.ToolParamType = ToolParamType
    types_mod.ToolParameterInfo = ToolParameterInfo

    sdk.types = types_mod
    sys.modules["maibot_sdk"] = sdk
    sys.modules["maibot_sdk.types"] = types_mod


_install_sdk_stubs()


def _load_plugin():
    name = "_req_plugin_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


plugin_module = _load_plugin()


class _FakeSend:
    def __init__(self, result=True, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    async def custom(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.exc is not None:
            raise self.exc
        return self.result


class _FakeLogger:
    def __init__(self):
        self.records = []

    def _record(self, level, msg, *args):
        self.records.append((level, msg % args if args else msg))

    def info(self, msg, *args):
        self._record("info", msg, *args)

    def warning(self, msg, *args):
        self._record("warning", msg, *args)

    def error(self, msg, *args):
        self._record("error", msg, *args)

    def debug(self, msg, *args):
        self._record("debug", msg, *args)


def _make_plugin(send=None, logger=None):
    plugin = plugin_module.AIVoicePlugin()
    plugin.ctx = SimpleNamespace(send=send or _FakeSend(), logger=logger or _FakeLogger())
    return plugin


def _raw(length=17):
    return bytes((i * 31 + 7) % 256 for i in range(length))


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def test_send_custom_receives_pure_base64_triple():
    raw = _raw(20)
    payload = _b64(raw)
    send = _FakeSend(result=True)
    plugin = _make_plugin(send=send)

    assert asyncio.run(plugin._send_voice(payload, "stream-1")) is True

    assert len(send.calls) == 1
    args, kwargs = send.calls[0]
    assert kwargs == {}
    assert len(args) == 3
    assert args[0] == "voice"
    assert args[2] == "stream-1"
    assert isinstance(args[1], str)
    assert "data:" not in args[1]
    assert "base64," not in args[1]
    assert base64.b64decode(args[1]) == raw


def test_send_custom_true_returns_true():
    plugin = _make_plugin(send=_FakeSend(result=True))
    assert asyncio.run(plugin._send_voice(_b64(_raw()), "sid")) is True


def test_send_custom_false_returns_false():
    plugin = _make_plugin(send=_FakeSend(result=False))
    assert asyncio.run(plugin._send_voice(_b64(_raw()), "sid")) is False


def test_send_custom_exception_returns_false_without_raising():
    plugin = _make_plugin(send=_FakeSend(exc=RuntimeError("adapter exploded")))
    assert asyncio.run(plugin._send_voice(_b64(_raw()), "sid")) is False


def test_send_failure_logs_stream_id():
    logger = _FakeLogger()
    plugin = _make_plugin(send=_FakeSend(exc=RuntimeError("boom")), logger=logger)
    asyncio.run(plugin._send_voice(_b64(_raw()), "stream-42"))

    messages = [msg for _level, msg in logger.records]
    assert any("Voice send failed: stream_id=stream-42" in msg for msg in messages)


def test_dict_payload_negative_control():
    """PR-before bug shape: passing a dict instead of a pure base64 string.

    send.custom("voice", {"file": "base64://..."}, stream_id) made the core run
    base64.b64decode(str(content)), which can never yield the original audio bytes.
    """
    raw = _raw(16)
    dict_payload = {"file": "base64://" + _b64(raw), "type": "voice"}
    send = _FakeSend(result=True)

    asyncio.run(send.custom("voice", dict_payload, "sid"))
    content = send.calls[0][0][1]

    try:
        decoded = base64.b64decode(str(content))
    except Exception:
        decoded = None

    assert decoded != raw


class _FakeTTSService:
    def __init__(self, audio_b64):
        self.audio_b64 = audio_b64

    async def synthesize_with_preset(self, **kwargs):
        return {"success": True, "audio_base64": self.audio_b64, "text": "hi"}

    async def synthesize_with_voice_clone(self, **kwargs):
        return {"success": True, "audio_base64": self.audio_b64, "text": "hi"}


def _preset_plugin(audio_b64, send_result=True):
    plugin = _make_plugin(send=_FakeSend(result=send_result))
    plugin.tts_service = _FakeTTSService(audio_b64)
    plugin.voices = {}
    plugin.default_voice = ""
    plugin.config = SimpleNamespace(
        voice=SimpleNamespace(
            voice_mode="preset",
            preset_voice="mimo_default",
            default_voice="",
            clone_voice="",
        )
    )
    return plugin


def test_voice_clone_tts_reports_sent_true():
    plugin = _preset_plugin(_b64(_raw(18)))
    result = asyncio.run(plugin.voice_clone_tts(text="hello", stream_id="s1"))
    assert result["success"] is True
    assert result["sent"] is True
    assert "error" not in result


def test_voice_clone_tts_reports_sent_false_and_warns():
    logger = _FakeLogger()
    plugin = _preset_plugin(_b64(_raw(18)), send_result=False)
    plugin.ctx.logger = logger
    result = asyncio.run(plugin.voice_clone_tts(text="hello", stream_id="s2"))

    assert result["sent"] is False
    assert result["error"] == "Voice send failed"
    messages = [msg for _level, msg in logger.records]
    assert any("Voice reply failed to send: stream_id=s2" in msg for msg in messages)


def test_voice_clone_tts_strips_data_prefix_defensively():
    raw = _raw(19)
    send = _FakeSend(result=True)
    plugin = _preset_plugin("data:audio/wav;base64," + _b64(raw))
    plugin.ctx.send = send

    asyncio.run(plugin.voice_clone_tts(text="hello", stream_id="s3"))

    assert len(send.calls) == 1
    content = send.calls[0][0][1]
    assert "data:" not in content
    assert base64.b64decode(content) == raw
