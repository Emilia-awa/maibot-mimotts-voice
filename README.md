# MiMo TTS Voice Plugin for MaiBot

基于小米 MiMo-V2.5-TTS 的 AI 语音服务插件，为 MaiBot 提供智能语音回复功能。支持**预置音色**和**音色复刻**两种模式。


## 功能特性(好用的话请点个star⭐~)

- 🎤 **预置音色**：内置 9 种精品音色（中文/英文，男声/女声），开箱即用
- 🎭 **音色复刻**：通过音频样本精准复刻任意音色，放入 `voices/` 目录即可
- 🤖 **AI 工具链暴露**：`send_voice_reply` 工具暴露在 AI 工具链中（`activation_type=ALWAYS`），AI 可自主决定何时使用语音回复
- 🎨 **AI 智能风格控制**：风格指令由 AI 根据角色人设和对话情境自行决定，无需用户手动配置
- 🎬 **导演模式**：支持从角色、场景、指导三个维度全方位刻画语音表演，AI 自动判断何时需要深度演绎
- ⚡ **异步发送**：语音合成和发送异步执行，不阻塞 AI 主循环
- 🔧 **自动配置初始化**：首次启动时自动从 `config.example.toml` 生成 `config.toml`，不覆盖用户已有配置

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

### 风格控制方式

风格控制由 AI 根据当前扮演的角色人设和对话情境**自行决定**，无需用户手动指定。AI 会自动判断何时需要风格指令，并选择合适的表达方式。

支持三种风格控制方式，AI 可自由组合使用：

**1. 自然语言风格指令**（AI 通过 `style_instruction` 参数传入）

AI 用自然语言描述语气、情绪、语速等，像给演员说戏一样：

- `一位温柔的少女，声音清甜软糯，语速偏慢，用安慰的语气`
- `语气俏皮活泼，带点小得意，语速偏快`
- `声音低沉严肃，像在教训人，语速慢一些`

**2. 导演模式**（AI 根据场景需要自动启用）

AI 从角色、场景、指导三个维度全方位刻画表演：

```
角色：一位温柔的大姐姐，性格体贴温暖，声音甜美有亲和力。
场景：安慰失恋的朋友。
指导：语调柔和温暖，气息松弛，偶尔带叹息，语速偏慢，尾音上扬带笑意。
```

**3. 音频标签**（AI 在 `reply_text` 中自动插入）

AI 在文本任意位置用括号标注语气/情绪/声音动作：

- 中文：`（紧张）呼……冷静。（叹气）算了。（轻笑）好吧好吧。`
- 英文：`(sighs) I don't know. (laughs) That's funny!`
- 整段风格：`（温柔）你好呀~` `（东北话）哎呀妈呀~` `（唱歌）歌词...`
- 常用标签：开心/悲伤/愤怒/温柔/慵懒/俏皮/磁性/沙哑/甜美/冷漠/叹气/轻笑/哽咽/深呼吸 等

> `style_instruction`（整体风格）+ `reply_text` 中的音频标签（句内细节）可同时使用，两者不冲突。

## 目录结构

```
maibot-mimotts-voice/
├── plugin.py           # 插件主入口
├── tts_service.py      # MiMo TTS 服务封装
├── config.toml         # 插件配置（gitignored）
├── config.example.toml # 配置示例
├── _manifest.json      # 插件清单
├── tests/              # 单元测试（pytest）
├── README.md           # 本文档
├── LICENSE             # MIT 许可证
├── .gitignore          # Git 忽略规则
├── requirements.txt    # Python 依赖
└── voices/             # 音色复刻文件目录（gitignored）
```

## 更新日志

### v1.7.0

- 🎙️ **语音发送修复**：`send.custom` 改为传递纯 base64 字符串，修复 SnowLuma / NapCat 适配器下
  `出站消息没有可转换的 OneBot 消息段` 与 `Failed to open input` 报错
- 🧩 **base64 补位修正**：先剥离 `data:` 前缀再对正文补位，修复部分长度下 `Incorrect padding`
- 📢 **发送结果可见**：语音发送失败不再静默，`voice_clone_tts` 返回 `sent` 字段并写 warning 日志
- 📋 **清单更正**：移除不存在的 `send.record` 能力声明与未使用的能力项

### v1.6.0

- 🔧 **工具链暴露**：`send_voice_reply` 工具暴露在 AI 工具链中，AI 可自主决定何时使用语音回复
- 🎬 **AI 智能风格控制**：风格指令由 AI 根据角色人设和对话情境自行决定，支持自然语言指令、导演模式、音频标签三种方式
- 🎨 **style_instruction 可选化**：AI 自行判断何时需要风格指令，无需每次填写
- 📋 **配置自动初始化**：首次启动自动从 `config.example.toml` 生成 `config.toml`

### v1.0.0

- 初始版本：预置音色、音色复刻、基础语音回复功能

## 注意事项

1. **API Key**：需要在 [小米 MiMo 平台](https://platform.xiaomimimo.com) 申请
2. **音色复刻**：建议录音时长不低于 30 秒，确保无背景噪音
3. **Base64 大小**：音色参考音频的 Base64 编码不能超过 10MB
4. **费用**：MiMo-V2.5-TTS 系列当前限时免费

## 许可证

MIT License
