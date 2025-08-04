#!/usr/bin/env python3

import os
import sys
import html
import re
from pathlib import Path

from subpython.asset_copy import copy_local_assets
from subpython.subset_fonts import run_subset_fonts

try:
    import yaml
except ImportError:
    sys.exit("PyYAML が見つかりません。pip install pyyaml でインストールしてください。")

# void elements（終了タグ不要）
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr"
}

def load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} はシーケンス（先頭が - の構造）である必要があります。")
    return data

def build_tree(nodes):
    indexed = list(enumerate(nodes))
    tag_map = {}
    for idx, node in indexed:
        tag = node.get("tag")
        tag_map.setdefault(tag, []).append(idx)

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

    child_idxs = children.get(idx, [])
    for cidx in child_idxs:
        _, child_node = indexed[cidx]
        inner_parts.append(render_node(cidx, child_node, children, indexed, indent + 2))

    indent_str = " " * indent
    if tag in VOID_ELEMENTS:
        return f'{indent_str}<{tag}{attr_str}>'
    else:
        if inner_parts:
            inner = "\n".join(inner_parts)
            if child_idxs:
                rendered = (
                    f'{indent_str}<{tag}{attr_str}>\n'
                    f'{inner}\n'
                    f'{indent_str}</{tag}>'
                )
            else:
                rendered = f'{indent_str}<{tag}{attr_str}>{inner}</{tag}>'
            return rendered
        else:
            return f'{indent_str}<{tag}{attr_str}></{tag}>'

def assemble_html(indexed, children):
    top_nodes = children.get(None, [])
    body = []
    for idx in top_nodes:
        _, node = indexed[idx]
        body.append(render_node(idx, node, children, indexed, indent=0))
    parts = ["<!DOCTYPE html>"] + body
    return "\n".join(parts) + "\n"

def to_root_relative(html_text: str) -> str:
    def repl(m):
        attr, quote, path = m.group(1), m.group(2), m.group(3)
        if path.startswith(("/", "http://", "https://", "data:")):
            return m.group(0)
        normalized = "/" + path.lstrip("./")
        return f'{attr}={quote}{normalized}{quote}'
    pattern = re.compile(r'(href|src)=(["\'])([^"\']+)(["\'])')
    return pattern.sub(lambda m: repl(m), html_text)

def gather_yaml_inputs(base_arg: str):
    p = Path(base_arg)
    if p.is_dir():
        yamls = list(p.rglob("*.yaml")) + list(p.rglob("*.yml"))
        return sorted({x for x in yamls})
    else:
        result = [p]
        pages_dir = Path("pages")
        if pages_dir.is_dir():
            extra = list(pages_dir.rglob("*.yaml")) + list(pages_dir.rglob("*.yml"))
            result.extend(extra)
        return sorted({x for x in result})

def compute_output_path(yaml_path: Path, outdir: Path) -> Path:
    if yaml_path.name.lower() in ("index.yaml", "index.yml"):
        return outdir / "index.html"
    try:
        if "pages" in yaml_path.parts:
            rel = yaml_path.relative_to("pages").with_suffix(".html")
            return outdir / "pages" / rel
    except Exception:
        pass
    return outdir / (yaml_path.stem + ".html")

def process_single_yaml(yaml_path: Path, outdir: Path):
    try:
        nodes = load_yaml(yaml_path)
    except Exception as e:
        print(f"YAML 読み込みに失敗しました ({yaml_path}): {e}", file=sys.stderr)
        return

    indexed, children = build_tree(nodes)
    html_text = assemble_html(indexed, children)
    html_text = to_root_relative(html_text)

    out_path = compute_output_path(yaml_path, outdir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
    print(f"HTML 出力: {out_path}")

    # asset_copy を YAML 親ディレクトリとプロジェクトルート両方で実行して、ルート側参照も拾う
    copy_local_assets(nodes, yaml_path.parent, outdir)
    copy_local_assets(nodes, Path("."), outdir)

    # サブセットフォント生成（フォントは ./fonts にある想定）
    try:
        run_subset_fonts(
            css_path="./style/fonts.css",
            index_yaml=str(yaml_path),
            dist_dir=str(outdir),
            fonts_source_dir="./fonts"
        )
        print(f"サブセットフォントを生成 ({yaml_path})")
    except Exception as e:
        print(f"サブセット生成でエラーが出ました ({yaml_path}): {e}", file=sys.stderr)

def main():
    import argparse

    parser = argparse.ArgumentParser(description="YAML から HTML を生成し、dist 以下に出力する。pages/ 以下も再帰的に処理し、パスをルート相対化する。")
    parser.add_argument("yaml", nargs="?", default="index.yaml", help="入力 YAML ファイルかディレクトリ。pages/ 以下も自動で含む。")
    parser.add_argument("--outdir", "-o", default="dist", help="出力先ディレクトリ（デフォルト: dist）")
    args = parser.parse_args()

    yaml_inputs = gather_yaml_inputs(args.yaml)
    if not yaml_inputs:
        sys.exit("処理対象の YAML が見つかりません。")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ルートの index.yaml を先に処理して基本資産をコピーしておく（必要なら）
    root_index = Path("index.yaml")
    if root_index.exists():
        process_single_yaml(root_index, outdir)

    for yaml_path in yaml_inputs:
        if not yaml_path.exists():
            print(f"スキップ: 存在しないファイル {yaml_path}", file=sys.stderr)
            continue
        # index.yaml は既に処理済みなら二度やらない
        if yaml_path.name.lower() in ("index.yaml", "index.yml") and yaml_path == root_index:
            continue
        process_single_yaml(yaml_path, outdir)

if __name__ == "__main__":
    main()
