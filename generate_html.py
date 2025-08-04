#!/usr/bin/env python3
from subpython.asset_copy import copy_local_assets

import os
import sys
import html
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML が見つかりません。pip install pyyaml でインストールしてください。")

# HTML では内容を持たない void elements（終了タグ不要）
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr"
}

def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise ValueError("index.yaml はシーケンス（先頭が - になる構造）である必要があります。")
    return data

def build_tree(nodes):
    # 各ノードに一意の内部 index を付ける
    indexed = list(enumerate(nodes))  # list of (idx, dict)
    # tag -> list of indices (for lookup)
    tag_map = {}
    for idx, node in indexed:
        tag = node.get("tag")
        tag_map.setdefault(tag, []).append(idx)

    # children mapping: parent_idx -> list of child indices; root uses None
    children = {}
    parent_of = {}

    for idx, node in indexed:
        parent_tag = node.get("parent")
        if parent_tag is None:
            raise ValueError(f"ノード {node} に parent がありません。")
        if parent_tag == "root":
            parent_idx = None
        else:
            candidates = tag_map.get(parent_tag, [])
            if not candidates:
                raise ValueError(f"親タグ '{parent_tag}' が見つかりません（子: {node}）。")
            if len(candidates) > 1:
                # 同じタグが複数ある場合は最初を使うが警告を出す
                print(f"警告: 親タグ '{parent_tag}' が複数あります。最初のものを使います。", file=sys.stderr)
            parent_idx = candidates[0]
        parent_of[idx] = parent_idx
        children.setdefault(parent_idx, []).append(idx)

    return indexed, children

def render_node(idx, node, children, indexed, indent=2):
    tag = node.get("tag")
    attrs = []
    for key, value in node.items():
        if key in ("tag", "parent", "text"):
            continue
        # 属性値を文字列化して escape
        val = str(value)
        escaped = html.escape(val, quote=True)
        attrs.append(f'{key}="{escaped}"')
    attr_str = ""
    if attrs:
        attr_str = " " + " ".join(attrs)

    inner_parts = []
    text = node.get("text")
    if text is not None:
        inner_parts.append(html.escape(str(text)))

    # 子要素があれば再帰
    child_idxs = children.get(idx, [])
    for cidx in child_idxs:
        _, child_node = indexed[cidx]
        inner_parts.append(render_node(cidx, child_node, children, indexed, indent + 2))

    indent_str = " " * indent
    if tag in VOID_ELEMENTS:
        # void element は中身を持たない（text があっても無視）
        return f'{indent_str}<{tag}{attr_str}>'
    else:
        if inner_parts:
            inner = "\n".join(inner_parts)
            # 子要素を持つときは改行付きの構成にする
            if child_idxs:
                rendered = (
                    f'{indent_str}<{tag}{attr_str}>\n'
                    f'{inner}\n'
                    f'{indent_str}</{tag}>'
                )
            else:
                # テキストのみならインライン
                rendered = f'{indent_str}<{tag}{attr_str}>{inner}</{tag}>'
            return rendered
        else:
            return f'{indent_str}<{tag}{attr_str}></{tag}>'

def assemble_html(indexed, children):
    # <html> 以下を children[None]
    top_nodes = children.get(None, [])
    body = []

    for idx in top_nodes:
        _, node = indexed[idx]
        body.append(render_node(idx, node, children, indexed, indent=0))

    # 先頭に <!DOCTYPE html>
    parts = ["<!DOCTYPE html>"] + body
    return "\n".join(parts) + "\n"

def main():
    import argparse

    parser = argparse.ArgumentParser(description="YAML から HTML を生成して dist/index.html に出力する。")
    parser.add_argument("yaml", nargs="?", default="index.yaml", help="入力の YAML ファイル（デフォルト: index.yaml）")
    parser.add_argument("--outdir", "-o", default="dist", help="出力ディレクトリ（デフォルト: dist）")
    args = parser.parse_args()

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        sys.exit(f"{yaml_path} が存在しません。")

    try:
        nodes = load_yaml(yaml_path)
    except Exception as e:
        sys.exit(f"YAML 読み込みに失敗しました: {e}")

    indexed, children = build_tree(nodes)
    html_text = assemble_html(indexed, children)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / "index.html"
    out_path.write_text(html_text, encoding="utf-8")

    # asset_copy
    indexed, children = build_tree(nodes)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ローカル参照されているファイル（style.css など）をコピー
    copy_local_assets(nodes, yaml_path.parent, outdir)
    html_text = assemble_html(indexed, children)

    out_path = outdir / "index.html"
    out_path.write_text(html_text, encoding="utf-8")
    print(f"出力しました: {out_path}")


if __name__ == "__main__":
    main()
