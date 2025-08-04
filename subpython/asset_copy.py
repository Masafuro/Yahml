# asset_copy.py（該当部分の修正）
from pathlib import Path
from urllib.parse import urlparse
import shutil
import sys
import os

def is_local_reference(ref: str) -> bool:
    if not isinstance(ref, str):
        return False
    if ref.startswith(("/", "#")):
        return False
    lower = ref.lower()
    if lower.endswith((".html", ".htm")):
        return False
    parsed = urlparse(ref)
    if parsed.scheme or ref.startswith("//"):
        return False
    return True

def normalize_rel_path(rel: Path) -> Path:
    norm = Path(os.path.normpath(str(rel)))
    parts = list(norm.parts)
    while parts and parts[0] == "..":
        parts.pop(0)
    if not parts:
        return Path(".")
    return Path(*parts)

def copy_local_assets(nodes, yaml_dir: Path, outdir: Path):
    seen = set()
    for node in nodes:
        for attr in ("href", "src"):
            val = node.get(attr)
            if not val or not is_local_reference(val):
                continue
            rel_path = Path(urlparse(val).path)

            # 試すベースディレクトリの順番：まず YAML 親、その次にプロジェクトルート
            src_path = None
            tried = []
            for base in (yaml_dir, Path(".")):
                candidate = (base / rel_path).resolve()
                tried.append(candidate)
                if candidate.exists() and candidate.is_file():
                    src_path = candidate
                    break

            if src_path is None:
                print(f"警告: 参照先ファイルが見つかりません: {val} (期待場所候補: {', '.join(str(p) for p in tried)})", file=sys.stderr)
                continue

            # コピー先は正規化して outdir 以下に
            dest_rel = normalize_rel_path(rel_path)
            dest_path = (outdir / dest_rel).resolve()

            # src と dest が同一ならスキップ
            try:
                if src_path == dest_path:
                    continue
            except Exception:
                pass

            # outdir を逸脱していないか念のため保証
            try:
                outdir_resolved = outdir.resolve()
                if not str(dest_path).startswith(str(outdir_resolved)):
                    dest_path = outdir_resolved / dest_rel
            except Exception:
                pass

            if dest_path in seen:
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src_path, dest_path)
                seen.add(dest_path)
            except Exception as e:
                print(f"エラー: ファイルをコピーできませんでした: {src_path} -> {dest_path} ({e})", file=sys.stderr)
