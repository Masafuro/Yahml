# asset_copy.py
from pathlib import Path
from urllib.parse import urlparse
import shutil
import sys

def is_local_reference(ref: str) -> bool:
    if not isinstance(ref, str):
        return False
    if ref.startswith(("/", "#")):
        return False
    parsed = urlparse(ref)
    if parsed.scheme or ref.startswith("//"):
        return False
    return True

def copy_local_assets(nodes, yaml_dir: Path, outdir: Path):
    seen = set()
    for node in nodes:
        for attr in ("href", "src"):
            val = node.get(attr)
            if not val or not is_local_reference(val):
                continue
            rel_path = Path(urlparse(val).path)
            src_path = (yaml_dir / rel_path).resolve()
            if not src_path.exists():
                print(f"警告: 参照先ファイルが見つかりません: {val} (期待場所: {src_path})", file=sys.stderr)
                continue
            if not src_path.is_file():
                print(f"警告: 参照先がファイルではありません: {src_path}", file=sys.stderr)
                continue
            dest_path = outdir / rel_path
            if dest_path in seen:
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, dest_path)
                seen.add(dest_path)
            except Exception as e:
                print(f"エラー: ファイルをコピーできませんでした: {src_path} -> {dest_path} ({e})", file=sys.stderr)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YAML に書かれた href/src を見てローカル資産をコピーする")
    parser.add_argument("yaml", nargs="?", default="index.yaml", help="入力 YAML（相対パス解決の基点）")
    parser.add_argument("--outdir", "-o", default="dist", help="出力先ディレクトリ")
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML が必要です。pip install pyyaml を実行してください。")

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        sys.exit(f"{yaml_path} が見つかりません。")

    with yaml_path.open(encoding="utf-8") as f:
        nodes = yaml.safe_load(f)
    if not isinstance(nodes, list):
        sys.exit("YAML はリスト形式である必要があります。")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    copy_local_assets(nodes, yaml_path.parent, outdir)
    print("コピー処理が完了しました。")
