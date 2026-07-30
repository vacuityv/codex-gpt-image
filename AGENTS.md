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

## 如果沙箱拦住了网络

安装必须联网（要从 GitHub 拉取）。如果你看到 `EPERM`、连接被拒或类似的沙箱网络错误：

**正确做法**：向用户申请提权（带网络访问）后重试上面的命令。交互式会话里用户点一下"允许"即可。

**不要**做这些：

- 不要改用手动拷贝文件的方式绕过（见下方禁止事项）。
- 不要建议 `npx skills add ...` 之类的第三方命令 —— 那些工具跟本项目的 `codex plugin`
  机制无关，照着跑装不出可用的插件。
- 如果确实拿不到网络权限，就如实告诉用户"沙箱不允许联网，安装失败"，并让他在**普通终端**里跑：

  ```bash
  bash <(curl -fsSL https://raw.githubusercontent.com/vacuityv/codex-gpt-image/main/install.sh)
  ```

  终端不受 Codex 沙箱限制。不要自己编别的命令。

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
