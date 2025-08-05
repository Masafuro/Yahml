# Yahml

Yahml（ヤームル）は、YAML形式でHTML構造を定義し、静的なHTMLファイルとサブセットフォントを自動生成する軽量のPythonベースジェネレータです。

## 特徴

- index.yaml : **YAMLでHTMLを書く**：構造・順序・属性を宣言的に定義可能
- generate_html.py : **静的サイト生成**：ビルドコマンドひとつで軽量なHTMLとフォントが完成
    - asset_copy.py : **参照アセットコピー** : distフォルダにアセットをコピー
    - subset_fonts.py：**フォント自動最適化**：CSSとテキストを解析してサブセットフォント（woff2）を生成
- analyze_tags.py : yamlファイルのparentによる構造を読み取ってmermaid記法の.mdファイルを作成。指定したファイルと同階層、同名の.mdとして出力される。

## 使い方
1. /style/fonts.cssにフォント設定を書く。
    - このとき、--subset-sourceを記入する。ここで記入したフォントはfontsフォルダから参照される。
2. index.yamlを書く。tag,　parentつまり、設置する親要素を指定する。headなどのほか、#containerなどのID要素も指定できる。また、htmlそのものの場合rootを指定する。pagesフォルダにindex.yaml以外のページを作成する。
3. generate_html.pyを実行する。distフォルダにhtmlが生成される。
4. preview.pyを実行するとブラウザで開くことができる。


