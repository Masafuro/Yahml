#!/usr/bin/env python3

import argparse
import sys
import webbrowser
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="dist/index.html を既定のブラウザで開く。必要なら HTTP サーバを立てる。")
    parser.add_argument("html", nargs="?", default="dist/index.html", help="開く HTML ファイル（デフォルト: dist/index.html）")
    parser.add_argument("--serve", "-s", action="store_true", help="簡易 HTTP サーバを起動して開く（file:// ではフォント制限が出るときに有効）")
    parser.add_argument("--port", "-p", type=int, default=8000, help="HTTP サーバ使用時のポート（デフォルト: 8000）")
    args = parser.parse_args()

    target = Path(args.html)

    if args.serve:
        if not target.exists():
            sys.exit(f"{target} が存在しません。")
        # dist ディレクトリをルートにしてサーブ
        serve_dir = target.parent
        try:
            import http.server
            import socketserver
        except ImportError:
            sys.exit("標準ライブラリの http.server を読み込めませんでした。")

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(serve_dir), **k)

        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            url = f"http://localhost:{args.port}/{target.name}"
            print(f"Serving {serve_dir} at {url}")
            webbrowser.open(url)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("サーバを停止します。")
    else:
        if not target.exists():
            sys.exit(f"{target} が存在しません。")
        uri = target.resolve().as_uri()
        webbrowser.open(uri)

if __name__ == "__main__":
    main()
