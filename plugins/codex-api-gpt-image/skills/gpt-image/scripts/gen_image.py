#!/usr/bin/env python3
"""用 OpenAI Images API（默认 gpt-image-2）生成 / 编辑图片，保存为本地文件。

纯标准库实现，不依赖 openai SDK，Python 3.8+ 可直接运行。

凭据解析顺序（第一个命中者生效，便于分享给不同环境的人）：
  1. 环境变量   GPT_IMAGE_API_KEY -> OPENAI_API_KEY
  2. 配置文件   ~/.codex/gpt-image.json   {"base_url": "...", "api_key": "..."}
  3. codex 配置 ~/.codex/config.toml 里当前 model_provider 的 bearer / base_url
  4. 兜底       https://api.openai.com/v1

base 解析顺序：
  GPT_IMAGE_BASE_URL -> OPENAI_BASE_URL -> gpt-image.json -> config.toml -> 官方

用法：
  # 文生图
  python3 gen_image.py -p "赛博朋克猫咪" -o cat.png
  # 尺寸 / 质量 / 张数
  python3 gen_image.py -p "一只柴犬" --size 1536x1024 --quality high -n 2 -o shiba.png
  # 图生图 / 编辑（可多张参考图，可选 mask）
  python3 gen_image.py -p "把背景换成雪山" --image in.png -o edited.png
  # 只看凭据从哪来，不发请求
  python3 gen_image.py --check
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

VALID_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}
VALID_QUALITY = {"low", "medium", "high", "auto"}

# 不少中转挂在 Cloudflare 后面，会拦默认的 Python-urllib UA（403 / error 1010）
USER_AGENT = "curl/8.4.0"

CODEX_HOME = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
SKILL_CONF = os.path.join(CODEX_HOME, "gpt-image.json")
CODEX_CONF = os.path.join(CODEX_HOME, "config.toml")
AUTH_CONF = os.path.join(CODEX_HOME, "auth.json")


def _load_skill_conf():
    try:
        with open(SKILL_CONF) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _load_codex_auth():
    """codex login --with-api-key 会把 key 写进 ~/.codex/auth.json。

    ChatGPT 登录写的是 tokens（OAuth），那种 token 不能用于 Images API，忽略。
    """
    try:
        with open(AUTH_CONF) as f:
            d = json.load(f)
    except Exception:
        return {}
    k = d.get("OPENAI_API_KEY")
    return {"api_key": k} if k and str(k).strip() else {}


def _load_codex_provider():
    """从 codex 的 config.toml 里取当前 provider 的 base_url 和 bearer。

    只做够用的解析：先定位 model_provider，再读对应的 [model_providers.X] 段。
    兼容 experimental_bearer_token / http_headers.Authorization / env_key 三种写法。
    """
    try:
        with open(CODEX_CONF) as f:
            text = f.read()
    except Exception:
        return {}

    m = re.search(r'^\s*model_provider\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        return {}
    name = m.group(1)

    sec = re.search(
        r'^\[model_providers\.' + re.escape(name) + r'\]\s*$(.*?)(?=^\[|\Z)',
        text, re.M | re.S)
    if not sec:
        return {}
    body = sec.group(1)

    out = {}
    b = re.search(r'^\s*base_url\s*=\s*"([^"]+)"', body, re.M)
    if b:
        out["base_url"] = b.group(1)

    tok = re.search(r'^\s*experimental_bearer_token\s*=\s*"([^"]+)"', body, re.M)
    if tok:
        out["api_key"] = tok.group(1)
    else:
        hdr = re.search(r'Authorization\s*=\s*"Bearer\s+([^"]+)"', body)
        if hdr:
            out["api_key"] = hdr.group(1)
        else:
            ek = re.search(r'^\s*env_key\s*=\s*"([^"]+)"', body, re.M)
            if ek and os.environ.get(ek.group(1)):
                out["api_key"] = os.environ[ek.group(1)]
    return out


def resolve():
    """返回 (base, key, base_src, key_src)。"""
    conf = _load_skill_conf()
    prov = _load_codex_provider()
    auth = _load_codex_auth()

    key = key_src = None
    for var in ("GPT_IMAGE_API_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(var)
        if v and v.strip():
            key, key_src = v.strip(), f"env:{var}"
            break
    if not key and conf.get("api_key"):
        key, key_src = conf["api_key"].strip(), "~/.codex/gpt-image.json"
    if not key and prov.get("api_key"):
        key, key_src = prov["api_key"].strip(), "~/.codex/config.toml"
    if not key and auth.get("api_key"):
        key, key_src = auth["api_key"].strip(), "~/.codex/auth.json"

    base = base_src = None
    for var in ("GPT_IMAGE_BASE_URL", "OPENAI_BASE_URL"):
        v = os.environ.get(var)
        if v and v.strip():
            base, base_src = v.strip(), f"env:{var}"
            break
    if not base and conf.get("base_url"):
        base, base_src = conf["base_url"], "~/.codex/gpt-image.json"
    if not base and prov.get("base_url"):
        base, base_src = prov["base_url"], "~/.codex/config.toml"
    if not base:
        base, base_src = "https://api.openai.com/v1", "默认"

    return base.rstrip("/"), key, base_src, key_src


def base_candidates(base):
    """有的中转 base_url 带 /v1（如 https://x.com/v1），有的是裸域名，两种都试。"""
    base = base.rstrip("/")
    if base.endswith("/v1"):
        return [base, base[: -len("/v1")].rstrip("/")]
    return [base + "/v1", base]


def save_images(data, out, n):
    """data: 响应里的 data 列表。兼容 b64_json 和 url 两种返回。"""
    paths = []
    root, ext = os.path.splitext(os.path.expanduser(out))
    ext = ext or ".png"
    for i, item in enumerate(data):
        b64 = item.get("b64_json")
        if b64:
            raw = base64.b64decode(b64)
        elif item.get("url"):
            req = urllib.request.Request(item["url"], headers={"User-Agent": USER_AGENT})
            raw = urllib.request.urlopen(req, timeout=180).read()
        else:
            continue
        path = f"{root}{ext}" if n == 1 else f"{root}_{i + 1}{ext}"
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw)
        paths.append(path)
    return paths


def post_json(url, payload, key):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=600)


def post_multipart(url, fields, files, key):
    boundary = "----gptimage" + base64.urlsafe_b64encode(os.urandom(12)).decode()
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp"}
    for field, path in files:
        path = os.path.expanduser(path)
        fname = os.path.basename(path)
        ctype = mime.get(os.path.splitext(fname)[1].lower(), "application/octet-stream")
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
                 f"filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
        with open(path, "rb") as f:
            body += f.read()
        body += b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}",
                 "User-Agent": USER_AGENT},
        method="POST",
    )
    return urllib.request.urlopen(req, timeout=600)


def main():
    ap = argparse.ArgumentParser(description="gpt-image 文生图 / 图生图（纯标准库）")
    ap.add_argument("-p", "--prompt", help="提示词")
    ap.add_argument("-o", "--out", default="image.png",
                    help="输出路径（默认 image.png；n>1 自动加 _1/_2 后缀）")
    ap.add_argument("--model", default="gpt-image-2", help="模型，默认 gpt-image-2")
    ap.add_argument("--size", default="1024x1024", choices=sorted(VALID_SIZES))
    ap.add_argument("--quality", default="auto", choices=sorted(VALID_QUALITY))
    ap.add_argument("-n", type=int, default=1, help="生成张数")
    ap.add_argument("--image", action="append", default=[],
                    help="参考图，可多次传，触发图生图/编辑模式")
    ap.add_argument("--mask", help="蒙版图（仅编辑模式，可选）")
    ap.add_argument("--check", action="store_true", help="只检查凭据来源，不发请求")
    args = ap.parse_args()

    base, key, base_src, key_src = resolve()

    if args.check:
        print(f"base = {base}   (来源: {base_src})")
        print(f"       实际会依次尝试: {', '.join(b + '/images/generations' for b in base_candidates(base))}")
        print(f"key  = {'已找到 ' + key[:8] + '…' if key else '未找到'}   (来源: {key_src or '无'})")
        if not key:
            print("\n找过的位置（都没有 key）：")
            print("  - 环境变量 GPT_IMAGE_API_KEY / OPENAI_API_KEY")
            print(f"  - {SKILL_CONF}")
            print(f"  - {CODEX_CONF} 当前 provider 的 bearer")
            print(f"  - {AUTH_CONF} 的 OPENAI_API_KEY")
            print("\n最省事的解法：写一个 " + SKILL_CONF + "，内容：")
            print('  {"base_url": "https://你的中转/v1", "api_key": "sk-..."}')
            print("\n注意：如果你是 ChatGPT 账号登录（auth.json 里是 tokens 而非")
            print("OPENAI_API_KEY），那种 OAuth token 不能用于 Images API，必须另配 key。")
        return

    if not args.prompt:
        sys.exit("错误：缺少 -p/--prompt（或用 --check 检查配置）")
    if not key:
        sys.exit(f"错误：未找到 API key。先跑 `python3 {sys.argv[0]} --check` 看配置方法。")

    sys.stderr.write(f"[gpt-image] base={base} ({base_src})  key来源={key_src}  model={args.model}\n")

    def send(b):
        if args.image:
            fields = {"model": args.model, "prompt": args.prompt, "n": str(args.n),
                      "size": args.size, "quality": args.quality}
            files = [("image[]", p) for p in args.image]
            if args.mask:
                files.append(("mask", args.mask))
            return post_multipart(f"{b}/images/edits", fields, files, key)
        payload = {"model": args.model, "prompt": args.prompt, "n": args.n,
                   "size": args.size, "quality": args.quality}
        return post_json(f"{b}/images/generations", payload, key)

    body = None
    last = None
    candidates = base_candidates(base)
    for i, b in enumerate(candidates):
        try:
            body = json.loads(send(b).read().decode())
            if b != base:
                sys.stderr.write(f"[gpt-image] 注意：{base} 不通，改用 {b} 成功。"
                                 f"建议把 base 固定成 {b}\n")
            break
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            last = f"HTTP {e.code}: {detail[:600]}"
            # 只有"路径不存在"才值得换 base 重试；401/429 等换了也没用
            if e.code in (404, 405) and i + 1 < len(candidates):
                sys.stderr.write(f"[gpt-image] {b} 返回 {e.code}，换个前缀再试\n")
                continue
            sys.exit(f"请求失败（{b}） {last}")
        except urllib.error.URLError as e:
            sys.exit(f"网络错误（{b}）: {e}")
    if body is None:
        sys.exit(f"请求失败，所有 base 都不通：{candidates}  最后错误：{last}")

    if body.get("error"):
        sys.exit(f"API 错误: {json.dumps(body['error'], ensure_ascii=False)[:800]}")
    data = body.get("data") or []
    if not data:
        sys.exit(f"无图片返回: {json.dumps(body, ensure_ascii=False)[:500]}")

    paths = save_images(data, args.out, args.n)
    if not paths:
        sys.exit("保存失败：响应里既无 b64_json 也无 url")
    if body.get("usage"):
        sys.stderr.write(f"[gpt-image] usage={json.dumps(body['usage'])}\n")
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
