"""AI Voice Service Plugin for MaiBot."""

import asyncio
import base64
from pathlib import Path
from typing import Any, Optional

from maibot_sdk import API, CONFIG_RELOAD_SCOPE_SELF, MaiBotPlugin, Tool, Field, PluginConfigBase
from maibot_sdk.types import ActivationType, ToolParameterInfo, ToolParamType

try:
    from .tts_service import MiMoTTSService
except ImportError:
    from tts_service import MiMoTTSService


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    enabled: bool = Field(default=True, description="是否启用")
    config_version: str = Field(default="1.0.0", description="配置版本")


class VoiceSectionConfig(PluginConfigBase):
    __ui_label__ = "语音设置"
    mimo_api_key: str = Field(default="", description="MiMo API Key")
    api_base_url: str = Field(
        default="https://token-plan-cn.xiaomimimo.com/v1",
        description="MiMo API地址",
        json_schema_extra={"label": "API地址"},
    )
    voice_mode: str = Field(default="clone", description="语音模式: 'clone'(音色复刻) 或 'preset'(预置音色)")
    preset_voice: str = Field(default="mimo_default", description="预置音色ID（仅preset模式生效）")
    voices_dir: str = Field(default="voices", description="音色目录路径（相对于插件目录）")
    default_voice: str = Field(default="", description="默认音色名称（clone模式下为音频文件名）")
    clone_voice: str = Field(default="", description="复刻音色文件名（clone模式下优先使用）")


class VoicePluginConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    voice: VoiceSectionConfig = Field(default_factory=VoiceSectionConfig)


class AIVoicePlugin(MaiBotPlugin):
    config_model = VoicePluginConfig

    def __init__(self) -> None:
        super().__init__()
        self.tts_service: Optional[MiMoTTSService] = None
        self.voices: dict[str, str] = {}
        self.default_voice: str = ""

    async def on_load(self) -> None:
        self._ensure_config_exists()
        self.ctx.logger.info("AI Voice Plugin loading...")
        api_key = self.config.voice.mimo_api_key
        if not api_key:
            self.ctx.logger.warning("MiMo API Key not configured")
        self.tts_service = MiMoTTSService(api_key=api_key, api_base_url=self.config.voice.api_base_url, logger=self.ctx.logger)
        self.default_voice = self.config.voice.default_voice or self.config.voice.clone_voice
        await self._load_voices()
        self.ctx.logger.info("AI Voice Plugin loaded: mode=%s, default_voice=%s, voices=%s",
            self.config.voice.voice_mode, self.default_voice, list(self.voices.keys()))

    def _ensure_config_exists(self) -> None:
        """如果用户目录下不存在 config.toml，则从 config.example.toml 复制生成。不会覆盖用户已有配置。"""
        import shutil
        plugin_dir = Path(__file__).parent
        config_path = plugin_dir / "config.toml"
        example_path = plugin_dir / "config.example.toml"
        if config_path.exists():
            return
        if example_path.exists():
            shutil.copy2(example_path, config_path)
            self.ctx.logger.info("Generated config.toml from config.example.toml")
        else:
            self.ctx.logger.warning("Neither config.toml nor config.example.toml found")

    async def on_unload(self) -> None:
        if self.tts_service:
            await self.tts_service.close()
            self.tts_service = None
        self.voices.clear()

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        if scope == CONFIG_RELOAD_SCOPE_SELF:
            self.ctx.logger.info("Plugin config updated: version=%s", version)
            if self.tts_service and self.config.voice.mimo_api_key:
                self.tts_service.update_api_key(self.config.voice.mimo_api_key)
                self.tts_service.update_api_base_url(self.config.voice.api_base_url)
            self.default_voice = self.config.voice.default_voice or self.config.voice.clone_voice
            await self._load_voices()
            self.ctx.logger.info("Config reloaded: mode=%s, default_voice=%s", self.config.voice.voice_mode, self.default_voice)

    async def _load_voices(self) -> None:
        voices_dir_str = self.config.voice.voices_dir
        plugin_dir = Path(__file__).parent
        voices_dir = plugin_dir / voices_dir_str
        self.ctx.logger.info("Loading voices from: %s (plugin_dir=%s)", voices_dir, plugin_dir)

        if not voices_dir.exists():
            self.ctx.logger.warning("Voices dir not found: %s, creating it", voices_dir)
            voices_dir.mkdir(parents=True, exist_ok=True)
            return

        self.ctx.logger.info("Voices dir exists: %s, contents: %s", voices_dir, [f.name for f in voices_dir.iterdir()])

        audio_files = list(voices_dir.glob("*.wav")) + list(voices_dir.glob("*.mp3"))
        if not audio_files:
            self.ctx.logger.warning("No audio files found in: %s", voices_dir)
            return

        self.voices.clear()
        for audio_file in audio_files:
            voice_name = audio_file.stem
            file_size = audio_file.stat().st_size
            # Detect MIME type from extension
            suffix = audio_file.suffix.lower()
            mime_type = "audio/wav" if suffix == ".wav" else "audio/mpeg"
            with open(audio_file, "rb") as f:
                audio_bytes = f.read()
            b64_data = base64.b64encode(audio_bytes).decode("ascii")
            # Store with MIME type prefix for API call
            self.voices[voice_name] = f"data:{mime_type};base64,{b64_data}"
            self.ctx.logger.info("Loaded voice: %s, raw=%dKB, b64=%dKB, mime=%s", voice_name, file_size // 1024, len(b64_data) // 1024, mime_type)

        if not self.default_voice and self.voices:
            self.default_voice = next(iter(self.voices))
            self.ctx.logger.info("Using default voice: %s", self.default_voice)

        self.ctx.logger.info("Voice loading complete, total %d voices, names=%s", len(self.voices), list(self.voices.keys()))

    async def _find_stream_id(self, kwargs: dict) -> str:
        """Find stream_id from various sources."""
        # Method 1: from kwargs (system may pass it)
        sid = kwargs.get("stream_id", "")
        if sid:
            self.ctx.logger.info("Got stream_id from kwargs: %s", sid)
            return str(sid)

        # Method 2: from kwargs message
        msg = kwargs.get("message", {})
        if isinstance(msg, dict):
            sid = msg.get("stream_id", "")
            if sid:
                self.ctx.logger.info("Got stream_id from message: %s", sid)
                return str(sid)

        # Method 3: try to find group stream
        try:
            streams = await self.ctx.chat.get_group_streams()
            if streams:
                sid = streams[0].get("stream_id", "")
                self.ctx.logger.info("Using first group stream: %s", sid)
                return str(sid)
        except Exception as e:
            self.ctx.logger.warning("chat.get_group_streams failed: %s", e)

        return ""

    async def _send_voice(self, audio_b64: str, stream_id: str) -> bool:
        """Send voice message using raw base64 (same approach as ling-tts-bot).

        send.custom("voice", raw_base64_string, stream_id) — not a dict with file path.
        """
        self.ctx.logger.info("Sending voice to stream=%s, b64_len=%d", stream_id, len(audio_b64))

        try:
            sent = await self.ctx.send.custom("voice", audio_b64, stream_id)
            self.ctx.logger.info("Sent via voice+base64, result=%s", sent)
            return bool(sent)
        except Exception as e:
            self.ctx.logger.warning("voice send failed: %s", e)

        self.ctx.logger.error("All voice send methods failed")
        return False

    def _resolve_voice(self, voice_name: str) -> tuple[str, str, str]:
        """解析音色名称，返回 (voice_key, audio_base64, mode)。
        mode: 'clone' 使用音色复刻, 'preset' 使用预置音色。
        """
        voice_mode = self.config.voice.voice_mode

        # 确定要使用的音色 key
        voice_key = voice_name if voice_name and voice_name != "default" else self.default_voice

        # clone 模式：从本地音频文件中查找参考音频
        if voice_mode == "clone":
            if voice_key and voice_key in self.voices:
                return voice_key, self.voices[voice_key], "clone"

            # clone_voice 配置兜底
            clone_fallback = self.config.voice.clone_voice
            if clone_fallback and clone_fallback in self.voices:
                self.ctx.logger.warning("Voice '%s' not found, using clone_voice config: '%s'", voice_key, clone_fallback)
                return clone_fallback, self.voices[clone_fallback], "clone"

            # 如果 voices 非空但指定的没有，报错而非静默切换
            if self.voices:
                available = list(self.voices.keys())
                self.ctx.logger.error("Voice '%s' not found in voices! Available: %s. "
                    "请在 config.toml 的 clone_voice 或 default_voice 中指定一个已有的音色名。", voice_key, available)
                return "", "", ""

            self.ctx.logger.error("No voices loaded! Please put .wav/.mp3 files in the voices/ directory.")
            return "", "", ""

        # preset 模式
        preset_id = voice_key or self.config.voice.preset_voice or "mimo_default"
        return preset_id, "", "preset"

    @API("voice_clone_tts", description="TTS with specified voice", version="1", public=True)
    async def voice_clone_tts(self, text: str, style_instruction: str = "", stream_id: str = "", voice_name: str = "") -> dict[str, Any]:
        if not self.tts_service:
            return {"success": False, "error": "TTS service not initialized"}

        if not text or not text.strip():
            return {"success": False, "error": "Empty text"}

        voice_key, ref_audio, mode = self._resolve_voice(voice_name)
        if not voice_key:
            return {"success": False, "error": "No voice configured. Check voice config."}

        self.ctx.logger.info("TTS request: mode=%s, voice_key=%s, text_len=%d, style_len=%d",
            mode, voice_key, len(text), len(style_instruction))

        try:
            if mode == "clone":
                result = await self.tts_service.synthesize_with_voice_clone(
                    text=text, reference_audio_base64=ref_audio, style_instruction=style_instruction,
                )
            else:
                result = await self.tts_service.synthesize_with_preset(
                    text=text, voice_id=voice_key, style_instruction=style_instruction,
                )

            # 释放参考音频引用
            ref_audio = ""

            success = result.get("success")
            error = result.get("error", "")
            audio_b64 = result.get("audio_base64", "")
            self.ctx.logger.info("TTS result: success=%s, audio_len=%d, error=%s", success, len(audio_b64), error)

            if success and audio_b64 and stream_id:
                # 提取纯 base64 数据
                if "base64," in audio_b64:
                    audio_b64 = audio_b64.split("base64,", 1)[1]
                    audio_b64 = audio_b64.strip()

                # 立即从 result 中移除大字段，避免双重内存占用
                result.pop("audio_base64", None)

                await self._send_voice(audio_b64, stream_id)
                audio_b64 = ""
            elif audio_b64:
                # 不需要发送时也清理
                result.pop("audio_base64", None)

            return result
        except Exception as e:
            self.ctx.logger.error("TTS failed: %s", e)
            return {"success": False, "error": str(e)}

    @Tool(
        "send_voice_reply",
        brief_description="使用语音回复用户，可选传入风格指令控制语气情绪",
        detailed_description=(
            "使用语音进行回复。当用户要求语音、用户发送了语音消息、或你认为当前场景适合语音回复时调用。\n"
            "必填参数：reply_text（回复文本）、msg_id（当前消息ID）。\n"
            "可选参数：style_instruction（语音风格指令），不传则使用默认音色自然朗读，需要更生动的表达时可填写。\n\n"
            "【风格控制】可通过 style_instruction 参数精细控制语音演绎效果，"
            "根据你当前扮演的角色人设和对话情境，主动提供完整的风格描述，让语音更拟人、更有感染力。\n\n"
            "支持三种风格控制方式，可自由组合：\n\n"
            "1. 自然语言风格指令（推荐）：用自然语言描述语气、情绪、语速等，像给演员说戏一样。\n"
            "   示例：'一位温柔的少女，声音清甜软糯，语速偏慢，用安慰的语气，带点关切'\n"
            "   示例：'语气俏皮活泼，带点小得意，语速偏快，声音明亮有活力'\n"
            "   示例：'声音低沉严肃，像在教训人，语速慢一些，带点长辈的威严'\n\n"
            "2. 导演模式（高级）：从角色、场景、指导三个维度全方位刻画表演，适合需要高度拟人化的场景。\n"
            "   示例：'角色：一位温柔的大姐姐，性格体贴温暖，声音甜美有亲和力。"
            "场景：安慰失恋的朋友。指导：语调柔和温暖，气息松弛，偶尔带叹息，语速偏慢，尾音上扬带笑意。'\n"
            "   示例：'角色：百年门阀的大小姐，声音冷冽有威压，说话语速极慢，每个字都像在舌尖滚过。"
            "场景：在祠堂面对企图带她私奔的男人。指导：实音重且硬，尾音处加入轻微气音透出疲惫。'\n\n"
            "3. 音频标签（在 reply_text 中使用）：在文本任意位置用括号标注语气/情绪/声音动作。\n"
            "   中文全角/半角均可：（紧张）呼……冷静。（叹气）算了。（轻笑）好吧好吧。\n"
            "   英文：(sighs) I don't know. (laughs) That's funny!\n"
            "   整段风格标签：在文本开头加（温柔）你好呀~ 或（东北话）哎呀妈呀~ 或（唱歌）歌词...\n"
            "   常用风格标签：开心/悲伤/愤怒/温柔/慵懒/俏皮/磁性/沙哑/甜美/冷漠/严肃/活泼/深沉 等\n"
            "   常用动作标签：叹气/轻笑/哽咽/深呼吸/咳嗽/打哈欠/低语/提高音量 等\n\n"
            "提示：style_instruction（整体风格）+ reply_text 中的音频标签（句内细节）可同时使用，两者不冲突。"
        ),
        activation_type=ActivationType.ALWAYS,
        parameters=[
            ToolParameterInfo(name="reply_text", param_type=ToolParamType.STRING, description="回复文本。可在文本中插入音频标签控制句内语气细节，如（叹气）（轻笑）（温柔）（紧张）等。", required=True),
            ToolParameterInfo(name="msg_id", param_type=ToolParamType.STRING, description="当前消息ID", required=True),
            ToolParameterInfo(
                name="style_instruction",
                param_type=ToolParamType.STRING,
                description=(
                    "（可选）语音风格指令，用自然语言描述语气、情绪、语速等，让语音更拟人。\n"
                    "不传则默认朗读。当你觉得需要更生动的表达时再填写。\n"
                    "简单用法：'温柔安慰的语气，语速稍慢'\n"
                    "导演模式：'角色：XX，性格XX。场景：XX。指导：语调XX，语速XX，气息XX。'\n"
                    "也可配合 reply_text 中的音频标签（叹气/轻笑/停顿等）使用。"
                ),
                required=False,
                default="",
            ),
        ],
    )
    async def send_voice_reply(self, reply_text: str, msg_id: str = "", style_instruction: str = "", **kwargs: Any) -> dict[str, Any]:
        # Find the correct stream_id
        stream_id = await self._find_stream_id(kwargs)
        if not stream_id:
            self.ctx.logger.error("Cannot find stream_id for msg_id=%s, kwargs_keys=%s", msg_id, list(kwargs.keys()))
            return {"success": False, "method": "voice", "error": "Cannot find chat stream"}

        self.ctx.logger.info("Using stream_id=%s for voice reply, text_len=%d", stream_id, len(reply_text))

        # Always use the configured default voice
        asyncio.create_task(self._async_voice_reply(reply_text, style_instruction, stream_id, ""))
        return {"success": True, "method": "voice", "error": ""}

    async def _async_voice_reply(self, text: str, style_instruction: str, stream_id: str, voice_name: str) -> None:
        """Send voice reply asynchronously."""
        try:
            result = await self.voice_clone_tts(text=text, style_instruction=style_instruction, stream_id=stream_id, voice_name=voice_name)
            self.ctx.logger.info("Async voice reply result: %s", result.get("success"))
        except Exception as e:
            self.ctx.logger.error("Async voice reply failed: %s", e)


def create_plugin() -> AIVoicePlugin:
    return AIVoicePlugin()