#!/usr/bin/env python3

import os
import sys
import html
import re
from pathlib import Path
import shutil

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
    id_map = {}

    for idx, node in indexed:
        tag = node.get("tag")
        tag_map.setdefault(tag, []).append(idx)
        node_id = node.get("id")
        if isinstance(node_id, str):
            id_map[node_id] = idx

    children = {}
    parent_of = {}

    def resolve_parent_spec(spec):
        if spec == "root":
            return None, []
        if isinstance(spec, dict):
            cand = []
            for idx, node in indexed:
                match = True
                if "tag" in spec and node.get("tag") != spec["tag"]:
                    match = False
                if "id" in spec and node.get("id") != spec["id"]:
                    match = False
                if match:
                    cand.append(idx)
        elif isinstance(spec, str):
            if spec.startswith("#"):
                target_id = spec[1:]
                idx = id_map.get(target_id)
                cand = [idx] if idx is not None else []
            elif "#" in spec:
                tag_part, id_part = spec.split("#", 1)
                cand = [
                    idx for idx, node in indexed
                    if node.get("tag") == tag_part and node.get("id") == id_part
                ]
            else:
                cand = tag_map.get(spec, [])
        else:
            cand = []

        if not cand:
            return None, []
        return cand[0], cand

    for idx, node in indexed:
        parent_spec = node.get("parent")
        if parent_spec is None:
            raise ValueError(f"ノード {node} に parent がありません。")
        parent_idx, candidates = resolve_parent_spec(parent_spec)
        if parent_spec == "root":
            parent_idx = None
        else:
            if parent_idx is None:
                raise ValueError(f"親指定 '{parent_spec}' が見つかりません（子: {node}）。")
            if len(candidates) > 1:
                print(f"警告: 親指定 '{parent_spec}' が複数あります。最初のものを使います。", file=sys.stderr)
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

def adjust_asset_paths(html_text: str, out_html_path: Path, outdir: Path) -> str:
    def repl(m):
        attr, quote, orig = m.group(1), m.group(2), m.group(3)
        if orig.startswith(("/", "http://", "https://", "data:")):
            return m.group(0)
        target = (outdir / orig.lstrip("./")).resolve()
        try:
            rel = os.path.relpath(target, start=out_html_path.parent)
        except Exception:
            rel = orig
        rel = rel.replace(os.sep, "/")
        return f'{attr}={quote}{rel}{quote}'
    pattern = re.compile(r'(href|src)=(["\'])([^"\']+)(["\'])')
    return pattern.sub(lambda m: repl(m), html_text)

def fix_page_links(html_text: str, yaml_to_output: dict, outdir: Path) -> str:
    valid_roots = set()
    basename_map = {}
    for yaml_path, out_path in yaml_to_output.items():
        rel = "/" + out_path.relative_to(outdir).as_posix()
        valid_roots.add(rel)
        basename = out_path.name
        basename_map[basename] = rel

    def repl(m):
        attr, quote, path = m.group(1), m.group(2), m.group(3)
        if not path.startswith("/"):
            return m.group(0)
        if path in valid_roots:
            return m.group(0)
        candidate = basename_map.get(Path(path).name)
        if candidate:
            return f'{attr}={quote}{candidate}{quote}'
        return m.group(0)
    pattern = re.compile(r'(href|src)=(["\'])(/[^"\']+)(["\'])')
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

def copy_static_dirs(outdir: Path):
    for dirname in ("style", "fonts"):
        src = Path(dirname)
        if src.is_dir():
            dest = outdir / dirname
            shutil.copytree(src, dest, dirs_exist_ok=True)

def process_single_yaml(yaml_path: Path, outdir: Path, yaml_to_output: dict):
    try:
        nodes = load_yaml(yaml_path)
    except Exception as e:
        print(f"YAML 読み込みに失敗しました ({yaml_path}): {e}", file=sys.stderr)
        return

    indexed, children = build_tree(nodes)
    html_text = assemble_html(indexed, children)
    html_text = fix_page_links(html_text, yaml_to_output, outdir)

    out_path = compute_output_path(yaml_path, outdir)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_text = adjust_asset_paths(html_text, out_path, outdir)
    out_path.write_text(html_text, encoding="utf-8")
    print(f"HTML 出力: {out_path}")

    # asset_copy を YAML 親ディレクトリとルート両方で実行してローカル参照資産を拾う
    copy_local_assets(nodes, yaml_path.parent, outdir)
    copy_local_assets(nodes, Path("."), outdir)

def main():
    import argparse

    parser = argparse.ArgumentParser(description="YAML から HTML を生成し、dist 以下に出力する。pages/ 以下も継承し、相対パスを自動で調整する。")
    parser.add_argument("yaml", nargs="?", default="index.yaml", help="入力 YAML ファイルかディレクトリ。pages/ 以下も自動で含む。")
    parser.add_argument("--outdir", "-o", default="dist", help="出力先ディレクトリ（デフォルト: dist）")
    args = parser.parse_args()

    yaml_inputs = gather_yaml_inputs(args.yaml)
    if not yaml_inputs:
        sys.exit("処理対象の YAML が見つかりません。")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ルートの static ディレクトリを先にコピー
    copy_static_dirs(outdir)

    # 各 YAML の出力パスを事前に決めてマッピング
    yaml_to_output = {}
    for y in yaml_inputs:
        yaml_to_output[y] = compute_output_path(y, outdir)

    # index.yaml を先に処理して共通資産を出す
    root_index = Path("index.yaml")
    if root_index.exists():
        process_single_yaml(root_index, outdir, yaml_to_output)

    for yaml_path in yaml_inputs:
        if not yaml_path.exists():
            print(f"スキップ: 存在しないファイル {yaml_path}", file=sys.stderr)
            continue
        if yaml_path.name.lower() in ("index.yaml", "index.yml") and yaml_path == root_index:
            continue
        process_single_yaml(yaml_path, outdir, yaml_to_output)

    # 全体の統合サブセットフォントを生成する
    all_nodes = []
    for y in yaml_inputs:
        try:
            nodes = load_yaml(y)
        except Exception:
            continue
        all_nodes.extend(nodes)

    merged_yaml = outdir / ".yahml_merged.yaml"
    with merged_yaml.open("w", encoding="utf-8") as f:
        yaml.safe_dump(all_nodes, f, allow_unicode=True, sort_keys=False)

    try:
        run_subset_fonts(
            css_path="./style/fonts.css",
            index_yaml=str(merged_yaml),
            dist_dir=str(outdir),
            fonts_source_dir="./fonts"
        )
        print("統合サブセットフォントを生成しました。")
    except Exception as e:
        print(f"統合サブセット生成でエラーが出ました: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
