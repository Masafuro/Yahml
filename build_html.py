import yaml
import os
from collections import defaultdict
from pathlib import Path

# ファイルパス
INPUT_FILE = "index.yaml"
OUTPUT_FILE = "dist/index.html"

# ディレクトリ作成
os.makedirs("dist", exist_ok=True)

# YAMLを読み込み
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    elements = yaml.safe_load(f)

# 要素をIDでマップ（内部的にユニークIDを付与）
id_map = {}
children_map = defaultdict(list)

for i, el in enumerate(elements):
    node_id = f"node_{i}"
    el["_id"] = node_id
    id_map[node_id] = el
    parent = el.get("parent", "root")
    children_map[parent].append(node_id)

# HTMLエスケープは簡易対応（必要ならhtml.escapeへ）
def escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# 要素をHTMLに変換する関数
def render_element(el):
    tag = el.get("tag")
    if not tag:
        return ""

    # 開始タグと属性
    attrs = []
    for key, val in el.items():
        if key in {"tag", "text", "parent", "_id"}:
            continue
        if isinstance(val, str):
            attrs.append(f'{key}="{escape(val)}"')

    open_tag = f"<{tag}" + (" " + " ".join(attrs) if attrs else "") + ">"
    close_tag = f"</{tag}>" if tag not in {"meta", "link", "br", "img", "input"} else ""

    # 子要素をレンダリング
    children_html = ""
    for child_id in children_map.get(el["_id"], []):
        children_html += render_element(id_map[child_id])

    # テキストと結合
    text = escape(el.get("text", ""))
    return f"{open_tag}{text}{children_html}{close_tag}"

# ルートから再帰生成
html_output = "<!DOCTYPE html>\n"
for node_id in children_map["root"]:
    html_output += render_element(id_map[node_id]) + "\n"

# ファイルに書き出し
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(html_output)

print(f"HTML生成完了: {OUTPUT_FILE}")
