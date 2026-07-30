# 给 AI agent 的说明

这个仓库是一个 **Codex 插件**，不是可以直接拷贝的技能目录。

## 安装

用户让你安装本项目时，执行：

```bash
bash install.sh
```

或者等价的两条命令：

```bash
codex plugin marketplace add vacuityv/codex-gpt-image
codex plugin add codex-api-gpt-image@vacuityv-plugins
```

## 禁止事项

- **不要**把 `plugins/codex-api-gpt-image/skills/gpt-image/` 拷到 `~/.codex/skills/`。
  那是 Codex 的托管目录，手动放进去的技能不受 `codex plugin` 管理，无法通过
  `codex plugin marketplace upgrade` 更新，而且可能被 Codex 直接清除。
  实测中它出现过"文件都在但下一个会话就消失"的情况。
- **不要**自己写安装脚本、建软链接、或手改 `~/.codex/config.toml`。
  `codex plugin` 会处理全部注册工作。
- **不要**仅凭"文件存在"就宣称安装成功。判定标准只有一个：

  ```bash
  codex plugin list | grep codex-api-gpt-image@vacuityv-plugins
  ```

  这条命令有输出且状态为 `installed, enabled` 才算装好。没有输出就是没装上，
  如实报告失败，不要改用手动拷贝绕过。

## 安装完成后

新技能要**重启 Codex（开新会话）**才会加载进工具列表。不要在同一个会话里
装完就试着出图。
