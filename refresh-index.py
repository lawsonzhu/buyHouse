#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描本目录下的 HTML 报告，重新生成 index.html 里的 FILES / DIRS 清单。

用法：
    python3 refresh-index.py          # 更新 index.html
    python3 refresh-index.py --check  # 只看会收录哪些文件，不写回

收录规则：
    · 本目录下所有 .html（跳过 index.html 与隐藏文件），按修改时间倒序
    · 标题取 <title>，描述取 meta description / 首个段落
    · 子目录生成“目录”卡片
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
SKIP = {"index.html"}
DESC_LIMIT = 64


def clean(text: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    text = re.sub(r"\s+", " ", text).strip()
    # 去标签后中文标点两侧常留空格，收一下
    return re.sub(r"\s*([：，。、；！？])\s*", r"\1", text)


def first(html: str, pattern: str) -> str:
    m = re.search(pattern, html, flags=re.S | re.I)
    return clean(m.group(1)) if m else ""


def kind_of(name: str) -> str:
    n = name.lower()
    if "体检" in name:
        return "小区体检"
    if "vs" in n or "对比" in name or "对撞" in name:
        return "对比分析"
    if "综合" in name:
        return "综合分析"
    if "报告" in name:
        return "调研报告"
    return "报告"


def describe(html: str) -> str:
    for pat in (r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
                r'<h1[^>]*>(.*?)</h1>',
                r'<p[^>]*>(.*?)</p>'):
        t = first(html, pat)
        if t:
            return t[:DESC_LIMIT] + ("…" if len(t) > DESC_LIMIT else "")
    return ""


def scan_files():
    items = []
    for p in sorted(ROOT.glob("*.html")):
        if p.name in SKIP or p.name.startswith("."):
            continue
        try:
            html = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            print(f"  ! 跳过 {p.name}: {e}", file=sys.stderr)
            continue
        st = p.stat()
        items.append({
            "path": p.name,
            "title": first(html, r"<title>(.*?)</title>") or p.stem,
            "kind": kind_of(p.name),
            "desc": describe(html),
            "size": f"{st.st_size / 1024:.1f} KB",
            "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "_mtime": st.st_mtime,
        })
    items.sort(key=lambda x: x["_mtime"], reverse=True)
    for it in items:
        it.pop("_mtime")
    return items


def scan_dirs():
    dirs = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        entry = f"{d.name}/index.html"
        if not (d / "index.html").exists():
            htmls = sorted(d.glob("*.html"))
            if not htmls:
                continue
            entry = f"{d.name}/{htmls[0].name}"
        dirs.append({"path": entry, "name": d.name})
    return dirs


def dump(name: str, data) -> str:
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f"/* {name}:BEGIN */\nconst {name} = {body};\n/* {name}:END */"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只列出识别到的文件，不写回")
    args = ap.parse_args()

    files, dirs = scan_files(), scan_dirs()
    print(f"目录：{ROOT}")
    for f in files:
        print(f"  · {f['title']}  [{f['kind']}]  {f['size']}  {f['date']}  <- {f['path']}")
    for d in dirs:
        print(f"  · [目录] {d['name']} -> {d['path']}")
    if not files and not dirs:
        print("  （没有可收录的文件）")

    if args.check:
        return
    if not INDEX.exists():
        sys.exit(f"找不到 {INDEX.name}，请先创建索引页。")

    html = INDEX.read_text(encoding="utf-8")
    for name, data in (("FILES", files), ("DIRS", dirs)):
        pat = re.compile(r"/\* %s:BEGIN \*/.*?/\* %s:END \*/" % (name, name), re.S)
        if not pat.search(html):
            sys.exit(f"index.html 里缺少 /* {name}:BEGIN */ 标记，无法写入。")
        html = pat.sub(lambda m, n=name, d=data: dump(n, d), html, count=1)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = re.sub(r'(<div class="path mono" id="dirPath">)(.*?)(</div>)',
                  lambda m: m.group(1) + str(ROOT) + m.group(3), html, count=1, flags=re.S)
    html = re.sub(r'(<span id="stamp"[^>]*>)索引更新于[^<]*(</span>)',
                  lambda m: m.group(1) + f"索引更新于 {stamp}" + m.group(2), html, count=1)

    INDEX.write_text(html, encoding="utf-8")
    print(f"\n已更新 {INDEX.name}：{len(files)} 个文档，{len(dirs)} 个目录。")


if __name__ == "__main__":
    main()
