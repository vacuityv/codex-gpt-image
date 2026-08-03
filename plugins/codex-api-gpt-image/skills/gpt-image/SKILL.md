---
name: "gpt-image"
description: "Generate or edit raster images by calling the OpenAI Images API (gpt-image-2) through a bundled dependency-free CLI. Use when the user asks to draw, generate, create, or edit a picture / illustration / photo / asset, and especially when the built-in `image_gen` hosted tool is not available in the session (custom model provider, relay, or API-key auth). Also use for image-to-image edits from reference files. Do not use when the task is better served by editing existing SVG/vector assets or drawing directly in HTML/CSS/canvas."
---

# gpt-image

调用 OpenAI Images API 出图，保存为本地文件。**纯标准库**，不需要 `openai` SDK、不需要 venv。

## 什么时候用这个而不是内置 `image_gen`

内置 `image_gen` 是 Responses API 的 hosted tool，只有当 codex 走 OpenAI 官方后端**并且**处于 ChatGPT 登录态时才会挂载。用自定义 provider / 中转 / API key 认证时，会话里根本不会出现这个工具 —— 这时用本技能。

判断方法：如果工具列表里没有 `image_gen`，直接用本技能，**不要**去问用户要 `OPENAI_API_KEY`，本技能自己会解析凭据。

## 用法

脚本在本技能目录下的 `scripts/gen_image.py`，用 `python3` 运行。

**先自检凭据**（不发请求、不花钱）：

```bash
python3 "<skill_dir>/scripts/gen_image.py" --check
```

**文生图：**

```bash
python3 "<skill_dir>/scripts/gen_image.py" \
  -p "提示词" --size 1536x1024 --quality high -o out.png
```

**图生图 / 编辑**（`--image` 可多次传，`--mask` 可选）：

```bash
python3 "<skill_dir>/scripts/gen_image.py" \
  -p "把背景换成雪山" --image in.png -o edited.png
```

脚本把保存的文件路径打印到 **stdout**（每行一个），日志走 stderr。

## 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `-p/--prompt` | 提示词（除 `--check` 外必填） | — |
| `-o/--out` | 输出路径；`n>1` 时自动加 `_1/_2` 后缀 | `image.png` |
| `--model` | 模型 | `gpt-image-2` |
| `--size` | `1024x1024` / `1536x1024`(横) / `1024x1536`(竖) / `auto` | `1024x1024` |
| `--quality` | `low` / `medium` / `high` / `auto` | `auto` |
| `-n` | 生成张数 | `1` |
| `--image` | 参考图，可多次传，触发图生图/编辑模式 | — |
| `--mask` | 蒙版，仅编辑模式 | — |
| `--check` | 只打印凭据来源，不发请求 | — |

`gpt-image-2` 不支持 `background=transparent`。需要真透明底就换 `--model gpt-image-1.5`，或者让它在纯色背景上出图后再抠。

## 凭据

脚本按顺序找，第一个命中即用，**技能本身不含任何 key**：

1. 环境变量 `GPT_IMAGE_API_KEY` → `OPENAI_API_KEY`
2. `~/.codex/gpt-image.json`
3. `~/.codex/config.toml` 里当前 `model_provider` 那一段的 bearer 和 `base_url`
   （兼容 `experimental_bearer_token`、`http_headers.Authorization`、`env_key` 三种写法）
4. `~/.codex/auth.json` 里的 `OPENAI_API_KEY`
5. 兜底官方 `https://api.openai.com/v1`

base 同理：`GPT_IMAGE_BASE_URL` → `OPENAI_BASE_URL` → json → config.toml → 官方。
base 带不带 `/v1` 都行，脚本会依次尝试两种前缀。

如果自检显示 key 未找到，先跑 `--check` 看它找过哪些位置，再让用户写
`~/.codex/gpt-image.json`。注意 ChatGPT 账号登录存的是 OAuth `tokens`，
那个不能用于 Images API，必须另配 key —— 这种情况重装插件没有任何用。

注意 codex 默认不会把 `*KEY*` 这类环境变量传给它执行的命令，所以**第 3 条（复用 config.toml）通常才是实际生效的那条** —— 这也让本技能对"已经在 codex 里配好中转"的人零配置可用。

## 流程规范

1. 出图后把文件放到用户要的位置；没指定就放当前工作目录。
2. 生成完**如实报告**：只报告脚本 stdout 里真实打印出来的路径。绝不要把已有的图复制改名当成新生成的结果。
3. 脚本报错就把 stderr 原样贴给用户，不要静默换方案。
