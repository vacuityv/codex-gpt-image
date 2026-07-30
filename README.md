# codex-gpt-image

给 Codex CLI 补上生图能力的插件。文生图 / 图生图，走 OpenAI Images API（默认 `gpt-image-2`）。

## 为什么需要它

Codex 内置的 `image_gen` 是 Responses API 的 **hosted tool**（服务端执行），只有当 codex 走 OpenAI 官方后端并且处于 ChatGPT 登录态时才会挂载到会话里。

如果你用自定义 `model_provider` / 第三方中转 / API key 认证，会话里根本不会出现这个工具，codex 只会告诉你"没有可用的内置图像生成工具"。自带的 `imagegen` 技能有个 CLI fallback，但它只解析 `b64_json` 返回，遇到返回图片 URL 的中转会直接崩，而且它的 SKILL.md 明令禁止修改。

这个插件补的就是这一段。

## 安装

```bash
codex plugin marketplace add <本仓库地址>
```

```bash
codex plugin add gpt-image@gpt-image-local
```

装完自检凭据（不发请求、不花钱）：

```bash
python3 ~/.codex/plugins/cache/gpt-image-local/gpt-image/0.1.0/skills/gpt-image/scripts/gen_image.py --check
```

之后在 codex 里正常说"画一张 xxx"即可，codex 会自己触发这个技能。

## 凭据配置

**本仓库不含任何 key。** 脚本按顺序找，第一个命中即用：

1. 环境变量 `GPT_IMAGE_API_KEY` → `OPENAI_API_KEY`
2. `~/.codex/gpt-image.json`
3. `~/.codex/config.toml` 里当前 `model_provider` 那一段的 bearer 和 `base_url`
4. 兜底官方 `https://api.openai.com/v1`

base 同理：`GPT_IMAGE_BASE_URL` → `OPENAI_BASE_URL` → json → config.toml → 官方。

**如果你已经在 codex 里配好了中转 provider，第 3 条会自动生效，装完不用做任何配置。**

否则二选一：

```bash
export GPT_IMAGE_API_KEY=sk-xxx
export GPT_IMAGE_BASE_URL=https://your-relay/v1   # 用官方则不必设
```

或者写 `~/.codex/gpt-image.json`（这是各人自己的文件，不随插件分发）：

```json
{ "base_url": "https://your-relay/v1", "api_key": "sk-xxx" }
```

注意：codex 默认不会把 `*KEY*` 这类环境变量传给它执行的命令，所以实际生效的通常是第 2、3 条。

## 直接用 CLI

```bash
S=~/.codex/plugins/cache/gpt-image-local/gpt-image/0.1.0/skills/gpt-image/scripts/gen_image.py

# 文生图
python3 "$S" -p "水墨风格，一匹马在沙漠奔跑" --size 1536x1024 --quality high -o horse.png

# 图生图 / 编辑
python3 "$S" -p "把背景换成雪山" --image in.png -o edited.png
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `-p/--prompt` | 提示词（除 `--check` 外必填） | — |
| `-o/--out` | 输出路径；`n>1` 时自动加 `_1/_2` 后缀 | `image.png` |
| `--model` | 模型 | `gpt-image-2` |
| `--size` | `1024x1024` / `1536x1024` / `1024x1536` / `auto` | `1024x1024` |
| `--quality` | `low` / `medium` / `high` / `auto` | `auto` |
| `-n` | 生成张数 | `1` |
| `--image` | 参考图，可多次传，触发编辑模式 | — |
| `--mask` | 蒙版，仅编辑模式 | — |
| `--check` | 只打印凭据来源，不发请求 | — |

保存路径打到 stdout（每行一个），日志走 stderr。

## 实现说明

- **纯标准库**，不依赖 `openai` SDK，不需要 venv，Python 3.8+ 可跑。
- 同时兼容 `b64_json` 和 `url` 两种响应（不少中转返回的是 URL）。
- 请求带 `curl` UA —— 中转常挂在 Cloudflare 后面，默认的 Python-urllib UA 会被拦（403 / error 1010）。
- `gpt-image-2` 不支持 `background=transparent`，要真透明底得换 `--model gpt-image-1.5`。

## 开发

改完插件源码后重装：

```bash
codex plugin remove gpt-image && codex plugin add gpt-image@gpt-image-local
```

不要把技能目录直接放到 `~/.codex/skills/` —— 那是 codex 托管目录，手动放进去的会被清掉。用户技能必须走 plugin 机制。

## 目录结构

```
.agents/plugins/marketplace.json          marketplace 清单
plugins/gpt-image/
├── .codex-plugin/plugin.json             插件元信息
└── skills/gpt-image/
    ├── SKILL.md                          技能说明（codex 读这个决定何时触发）
    └── scripts/gen_image.py              出图脚本
```
