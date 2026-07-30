#!/usr/bin/env bash
# 本项目的唯一正确安装方式。直接执行：bash install.sh
#
# 不要把 skills/ 手动拷到 ~/.codex/skills/ —— 那是 Codex 的托管目录，
# 手动放进去的技能不受 codex plugin 管理，也可能被 Codex 清除。
set -euo pipefail

MARKET="vacuityv-plugins"
PLUGIN="codex-api-gpt-image"
SOURCE="${GPT_IMAGE_SOURCE:-vacuityv/codex-gpt-image}"

if ! command -v codex >/dev/null 2>&1; then
  echo "✗ 找不到 codex 命令，请先安装 Codex CLI。" >&2
  exit 1
fi

echo "→ 注册 marketplace: $SOURCE"
codex plugin marketplace add "$SOURCE" 2>&1 | sed 's/^/  /' || true

echo "→ 安装插件: $PLUGIN@$MARKET"
codex plugin add "$PLUGIN@$MARKET" 2>&1 | sed 's/^/  /'

echo
echo "→ 核实注册状态（codex plugin list）"
STATUS=$(codex plugin list 2>&1 | grep -F "$PLUGIN@$MARKET" || true)
if [ -z "$STATUS" ]; then
  echo "✗ 安装失败：$PLUGIN@$MARKET 未出现在 codex plugin list 中。" >&2
  echo "  请把上面的输出贴出来排查，不要改用手动拷贝的方式。" >&2
  exit 1
fi
echo "  $STATUS"

SCRIPT="$HOME/.codex/plugins/cache/$MARKET/$PLUGIN/0.1.0/skills/gpt-image/scripts/gen_image.py"
echo
echo "→ 凭据自检（不发请求、不产生费用）"
if [ -f "$SCRIPT" ]; then
  python3 "$SCRIPT" --check 2>&1 | sed 's/^/  /'
else
  echo "  ! 未找到脚本 $SCRIPT，版本号可能已变，请用 codex plugin list 的路径自行确认。" >&2
fi

echo
echo "✓ 安装完成。重启 Codex 后新技能才会加载，然后直接说「画一张 xxx」即可。"
