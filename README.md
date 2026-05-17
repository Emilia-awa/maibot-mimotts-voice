# MiMo TTS Voice Plugin for MaiBot

基于小米 MiMo-V2.5-TTS 的 AI 语音服务插件，为 MaiBot 提供智能语音回复功能。支持**预置音色**和**音色复刻**两种模式。

## 功能特性(好用的话请点个star⭐~)

- 🎤 **预置音色**：内置 9 种精品音色（中文/英文，男声/女声），开箱即用
- 🎭 **音色复刻**：通过音频样本精准复刻任意音色，放入 `voices/` 目录即可
- 🤖 **AI 自主决策**：提供 `send_voice_reply` 工具，AI 根据上下文判断是否使用语音
- 🎨 **风格控制**：支持自然语言指令控制语音风格（情绪、语速、语气等）
- ⚡ **异步发送**：语音合成和发送异步执行，不阻塞 AI 主循环

## 安装

### 1. 复制插件到 MaiBot

```bash
cd /path/to/MaiBot/plugins/
git clone https://github.com/Emilia-awa/maibot-mimotts-voice.git
```

### 2. 安装依赖

```bash
pip install aiohttp
```

### 3. 配置

编辑 `config.toml`（可从 `config.example.toml` 复制）：

```toml
[plugin]
enabled = true
config_version = "1.0.0"

[voice]
mimo_api_key = "your_api_key_here"
api_base_url = "https://token-plan-cn.xiaomimimo.com/v1"
voice_mode = "preset"
preset_voice = "冰糖"
voices_dir = "voices"
clone_voice = ""
```

### 4. 重启 MaiBot

插件会自动加载。

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mimo_api_key` | MiMo API Key（必填） | - |
| `api_base_url` | API 地址 | `https://token-plan-cn.xiaomimimo.com/v1` |
| `voice_mode` | 音色模式：`preset` 或 `clone` | `preset` |
| `preset_voice` | 预置音色名称（preset 模式） | `mimo_default` |
| `voices_dir` | 音色复刻目录（clone 模式，相对于插件目录） | `voices` |
| `clone_voice` | 指定复刻音色文件名（留空使用第一个文件） | - |

### API 地址

| 用户类型 | 地址 |
|---------|------|
| Plan 用户（包月/套餐） | `https://token-plan-cn.xiaomimimo.com/v1` |
| 按量计费用户 | `https://api.xiaomimimo.com/v1` |

## 音色模式

### 预置音色（preset）

无需额外配置，直接在 `preset_voice` 中填入音色名称：

| 音色名 | 语言 | 性别 |
|--------|------|------|
| `mimo_default` | 中文 | 女性（冰糖） |
| `冰糖` | 中文 | 女性 |
| `茉莉` | 中文 | 女性 |
| `苏打` | 中文 | 男性 |
| `白桦` | 中文 | 男性 |
| `Mia` | 英文 | 女性 |
| `Chloe` | 英文 | 女性 |
| `Milo` | 英文 | 男性 |
| `Dean` | 英文 | 男性 |

### 音色复刻（clone）

1. 将 `voice_mode` 改为 `clone`
2. 将参考音频文件放入 `voices/` 目录（支持 WAV 和 MP3）
3. 文件名即为音色名称，建议录音时长 30 秒以上

```
plugins/maibot-mimotts-voice/voices/
└── salt.wav    # 音色名称: salt
```

## 工具说明

插件提供 `send_voice_reply` 工具给 AI，AI 会根据对话上下文自行判断是否调用。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reply_text` | string | ✅ | 要合成语音的回复文本 |
| `msg_id` | string | ✅ | 当前消息 ID，用于自动查找聊天流 |
| `style_instruction` | string | ❌ | 语音风格指令 |

### 风格控制示例

- `用温柔的语气说`
- `语速稍快，带着兴奋`
- `低沉、神秘的声音`
- `用东北话说`
- `(开心)今天天气真好！`

## 目录结构

```
maibot-mimotts-voice/
├── plugin.py           # 插件主入口
├── tts_service.py      # MiMo TTS 服务封装
├── config.toml         # 插件配置（gitignored）
├── config.example.toml # 配置示例
├── _manifest.json      # 插件清单
├── README.md           # 本文档
├── LICENSE             # MIT 许可证
├── .gitignore          # Git 忽略规则
├── requirements.txt    # Python 依赖
└── voices/             # 音色复刻文件目录（gitignored）
```

## 注意事项

1. **API Key**：需要在 [小米 MiMo 平台](platform.xiaomimimo.com) 申请
2. **音色复刻**：建议录音时长不低于 30 秒，确保无背景噪音
3. **Base64 大小**：音色参考音频的 Base64 编码不能超过 10MB
4. **费用**：MiMo-V2.5-TTS 系列当前限时免费

## 许可证

MIT License
