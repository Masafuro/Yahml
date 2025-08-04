# subpython/subset_fonts.py

import sys
import os
from pathlib import Path
import yaml
import tinycss2
from fontTools import ttLib
from fontTools.subset import Subsetter, Options
import csv

def parse_css_fonts(css_path: Path):
    text = css_path.read_text(encoding="utf-8")
    rules = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)

    font_face_map = {}
    class_to_family = {}

    for rule in rules:
        if rule.type == "at-rule" and rule.at_keyword.lower() == "font-face":
            declarations = tinycss2.parse_declaration_list(rule.content)
            family = None
            subset_source = None
            subset_output = None

            for decl in declarations:
                if decl.type != "declaration":
                    continue
                name = decl.lower_name
                if name == "font-family":
                    val = serialize_font_family(decl.value)
                    family = val.strip().strip("'\"")
                elif name == "--subset-source":
                    subset_source = extract_custom_prop_value(decl.value)
                elif name == "src":
                    subset_output = extract_src_url(decl.value)

            if family:
                font_face_map[family] = {
                    "subset_source": subset_source,
                    "subset_output": subset_output,
                }
        elif rule.type == "qualified-rule":
            selector_str = tinycss2.serialize(rule.prelude).strip()
            class_names = extract_class_names_from_selector(selector_str)
            if not class_names:
                continue
            declarations = tinycss2.parse_declaration_list(rule.content)
            font_family_value = None
            for decl in declarations:
                if decl.type != "declaration":
                    continue
                if decl.lower_name == "font-family":
                    font_family_value = serialize_font_family(decl.value)
                    break
            if font_family_value:
                primary = font_family_value.split(",")[0].strip().strip("'\"")
                for cls in class_names:
                    class_to_family[cls] = primary

    return font_face_map, class_to_family

def serialize_font_family(tokens):
    return tinycss2.serialize(tokens)

def extract_custom_prop_value(tokens):
    text = tinycss2.serialize(tokens).strip()
    if text.startswith(("'", '"')) and text.endswith(("'", '"')):
        text = text[1:-1]
    return text

def extract_src_url(tokens):
    for t in tokens:
        if t.type == "url":
            return t.value
        if t.type == "function" and t.name.lower() == "url":
            inner = tinycss2.serialize(t.arguments).strip()
            if inner.startswith(("'", '"')) and inner.endswith(("'", '"')):
                inner = inner[1:-1]
            return inner
    full = tinycss2.serialize(tokens)
    import re
    m = re.search(r"url\(\s*['\"]?([^'\"\)]+)['\"]?\s*\)", full)
    if m:
        return m.group(1)
    return None

def extract_class_names_from_selector(selector: str):
    import re
    return re.findall(r"\.([A-Za-z0-9_\-]+)", selector)

def load_index_yaml(yaml_path: Path):
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        raise ValueError("index.yaml はリスト形式である必要があります。")
    return data

def collect_texts_per_class(index_nodes):
    class_texts = {}
    for node in index_nodes:
        cls_field = node.get("class") or node.get("className") or ""
        if not cls_field:
            continue
        class_names = str(cls_field).split()
        text = node.get("text", "")
        if not text:
            continue
        for cls in class_names:
            class_texts.setdefault(cls, []).append(str(text))
    for k in list(class_texts.keys()):
        class_texts[k] = "".join(class_texts[k])
    return class_texts

def build_family_codepoints(class_to_family, class_texts):
    family_texts = {}
    for cls, text in class_texts.items():
        family = class_to_family.get(cls)
        if not family:
            continue
        family_texts.setdefault(family, []).append(text)
    family_codepoints = {}
    for family, texts in family_texts.items():
        combined = "".join(texts)
        codepoints = set(combined)
        family_codepoints[family] = codepoints
    return family_codepoints

def subset_font(src_path: Path, dest_path: Path, codepoints_set: set):
    if not src_path.exists():
        print(f"エラー: 元フォントが見つかりません: {src_path}", file=sys.stderr)
        return False
    try:
        font = ttLib.TTFont(str(src_path))
    except Exception as e:
        print(f"フォント読み込み失敗: {src_path} ({e})", file=sys.stderr)
        return False

    options = Options()
    options.flavor = "woff2"
    options.with_zopfli = False
    subsetter = Subsetter(options=options)
    text = "".join(sorted(codepoints_set))
    subsetter.populate(text=text)
    subsetter.subset(font)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    try:
        font.save(str(dest_path))
    except Exception as e:
        print(f"サブセットフォント保存失敗: {dest_path} ({e})", file=sys.stderr)
        return False
    print(f"サブセット生成: {dest_path} (元: {src_path}, {len(codepoints_set)}文字)", file=sys.stderr)
    return True

def write_debug_csvs(dist_dir: Path, class_table: dict, family_codepoints: dict, font_face_map: dict):
    dist_dir.mkdir(parents=True, exist_ok=True)
    classes_csv = dist_dir / "subset_debug_classes.csv"
    families_csv = dist_dir / "subset_debug_families.csv"

    # クラスごと
    with classes_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "class_name", "font_family", "raw_text", "class_codepoints",
            "subset_source", "subset_output"
        ])
        for cls, entry in class_table.items():
            font_family = entry.get("font_family", "")
            raw_text = entry.get("raw_text", "")
            class_codepoints = "".join(sorted(set(raw_text)))
            subset_source = ""
            subset_output = ""
            face = font_face_map.get(font_family, {})
            subset_source = face.get("subset_source") or ""
            subset_output = face.get("subset_output") or ""
            writer.writerow([
                cls, font_family, raw_text, class_codepoints,
                subset_source, subset_output
            ])

    # フォントファミリごと
    with families_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "font_family", "combined_codepoints", "count", "subset_source", "subset_output"
        ])
        for family, codepoints in family_codepoints.items():
            face = font_face_map.get(family, {})
            subset_source = face.get("subset_source") or ""
            subset_output = face.get("subset_output") or ""
            combined = "".join(sorted(codepoints))
            writer.writerow([
                family, combined, len(codepoints), subset_source, subset_output
            ])

def run_subset_fonts(css_path: str, index_yaml: str, dist_dir: str, fonts_source_dir: str = "."):
    css_path = Path(css_path)
    index_yaml = Path(index_yaml)
    dist_dir = Path(dist_dir)
    fonts_source_dir = Path(fonts_source_dir)

    if not css_path.exists():
        raise FileNotFoundError(f"CSS が見つかりません: {css_path}")
    if not index_yaml.exists():
        raise FileNotFoundError(f"index.yaml が見つかりません: {index_yaml}")

    font_face_map, class_to_family = parse_css_fonts(css_path)
    class_texts = collect_texts_per_class(load_index_yaml(index_yaml))

    class_table = {}
    for cls, raw_text in class_texts.items():
        family = class_to_family.get(cls)
        class_table[cls] = {
            "font_family": family,
            "raw_text": raw_text,
        }

    family_codepoints = build_family_codepoints(class_to_family, class_texts)

    for family, codepoints in family_codepoints.items():
        face = font_face_map.get(family)
        if not face:
            print(f"警告: @font-face 定義が見つかりません: font-family '{family}' を使うクラスがあるが対応する @font-face がありません。", file=sys.stderr)
            continue
        subset_source_name = face.get("subset_source")
        subset_output_rel = face.get("subset_output")
        if not subset_source_name:
            print(f"警告: --subset-source がありません: font-family '{family}' の @font-face に元フォント指定がないためスキップします。", file=sys.stderr)
            continue
        if not subset_output_rel:
            print(f"警告: src (出力先) がありません: font-family '{family}' の @font-face に src がないためスキップします。", file=sys.stderr)
            continue

        src_path = (fonts_source_dir / subset_source_name).resolve()
        dest_path = (dist_dir / subset_output_rel).resolve()
        subset_font(src_path, dest_path, codepoints)

    # CSV 出力（完了後の状態を人が見られるように）
    write_debug_csvs(dist_dir, class_table, family_codepoints, font_face_map)

    return {
        "class_table": class_table,
        "family_codepoints": family_codepoints,
        "font_face_map": font_face_map,
        "class_to_family": class_to_family,
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CSS と index.yaml からサブセットフォントを生成する")
    parser.add_argument("--css", default="./style/fonts.css", help="元の CSS（@font-face とクラス定義を含む）")
    parser.add_argument("--index", default="index.yaml", help="index.yaml のパス")
    parser.add_argument("--dist", default="dist", help="出力先 dist ディレクトリ")
    parser.add_argument("--font-dir", default=".", help="元フォントを探すディレクトリ")
    args = parser.parse_args()

    run_subset_fonts(args.css, args.index, args.dist, args.font_dir)
