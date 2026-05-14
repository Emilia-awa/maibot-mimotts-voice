"""MiMo TTS Service Module - 支持预置音色和音色复刻"""

import logging
from typing import Any, Optional

import aiohttp


class MiMoTTSService:
    """MiMo TTS Service."""

    DEFAULT_API_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
    MODEL_PRESET = "mimo-v2.5-tts"
    MODEL_CLONE = "mimo-v2.5-tts-voiceclone"

    def __init__(self, api_key: str, api_base_url: str = "", logger: Optional[logging.Logger] = None):
        self.api_key = api_key.strip() if api_key else ""
        self.api_base_url = api_base_url.strip() if api_base_url else self.DEFAULT_API_BASE_URL
        self.logger = logger or logging.getLogger(__name__)
        self._session: Optional[aiohttp.ClientSession] = None

    def update_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip() if api_key else ""

    def update_api_base_url(self, api_base_url: str) -> None:
        self.api_base_url = api_base_url.strip() if api_base_url else self.DEFAULT_API_BASE_URL

    async def synthesize_with_preset(
        self,
        text: str,
        voice_id: str = "mimo_default",
        style_instruction: str = "",
        audio_format: str = "wav",
    ) -> dict[str, Any]:
        """使用预置音色合成语音"""
        if not self.api_key:
            return {"success": False, "error": "API Key not configured"}

        key_preview = self.api_key[:4] + "****" if len(self.api_key) > 4 else "empty"
        self.logger.info("Preset TTS: url=%s, key=%s, voice=%s", self.api_base_url, key_preview, voice_id)

        messages = []
        if style_instruction:
            messages.append({"role": "user", "content": style_instruction})
        else:
            messages.append({"role": "user", "content": ""})
        messages.append({"role": "assistant", "content": text})

        payload = {
            "model": self.MODEL_PRESET,
            "modalities": ["text", "audio"],
            "messages": messages,
            "audio": {
                "format": audio_format,
                "voice": voice_id,
            },
        }

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        return await self._do_request(payload, headers)

    async def synthesize_with_voice_clone(
        self,
        text: str,
        reference_audio_base64: str,
        style_instruction: str = "",
        audio_format: str = "wav",
    ) -> dict[str, Any]:
        """使用音色复刻合成语音"""
        if not self.api_key:
            return {"success": False, "error": "API Key not configured"}

        key_preview = self.api_key[:4] + "****" if len(self.api_key) > 4 else "empty"
        self.logger.info("Clone TTS: url=%s, key=%s", self.api_base_url, key_preview)

        messages = []
        if style_instruction:
            messages.append({"role": "user", "content": style_instruction})
        else:
            messages.append({"role": "user", "content": ""})
        messages.append({"role": "assistant", "content": text})

        voice_str = reference_audio_base64 if reference_audio_base64.startswith("data:") else f"data:audio/wav;base64,{reference_audio_base64}"
        self.logger.info("Voice string length: %d", len(voice_str))

        payload = {
            "model": self.MODEL_CLONE,
            "modalities": ["text", "audio"],
            "messages": messages,
            "audio": {
                "format": audio_format,
                "voice": voice_str,
            },
        }

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        return await self._do_request(payload, headers)

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建复用的 ClientSession"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """关闭 HTTP session，释放资源"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _do_request(self, payload: dict, headers: dict) -> dict[str, Any]:
        """执行API请求"""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.api_base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error("API failed: status=%s, body=%s", response.status, error_text[:200])
                    return {"success": False, "error": f"API failed: {response.status} - {error_text[:200]}"}

                result = await response.json()
                choices = result.get("choices", [])
                if not choices:
                    return {"success": False, "error": "No result"}

                message = choices[0].get("message", {})
                audio_data = message.get("audio", {})
                if not audio_data:
                    return {"success": False, "error": "No audio data"}

                audio_base64 = audio_data.get("data", "")
                if not audio_base64:
                    return {"success": False, "error": "Empty audio"}

                return {
                    "success": True,
                    "audio_base64": audio_base64,
                    "text": payload["messages"][-1]["content"],
                }

        except aiohttp.ClientError as e:
            self.logger.error("Network error: %s", e)
            return {"success": False, "error": f"Network error: {e}"}
        except Exception as e:
            self.logger.error("TTS error: %s", e)
            return {"success": False, "error": str(e)}
