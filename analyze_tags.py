import yaml
import os

def yaml_to_mermaid(input_path: str) -> str:
    # YAML の読み込み
    with open(input_path, 'r', encoding='utf-8') as f:
        docs = yaml.safe_load(f)

    # id をキーに要素マッピング
    id_map = {item['id']: item for item in docs if 'id' in item}

    # 特殊タグ（連番不要）
    special_tags = {'html', 'head', 'body'}

    # タグごとのカウンタとノード名登録
    tag_counters = {}
    node_names = {}
    for item in docs:
        tag = item.get('tag')
        if not tag:
            continue
        id_ = item.get('id')
        # html, head, body は連番をつけずタグ名のみ
        if tag in special_tags:
            node_name = tag
        elif id_:
            node_name = f"{tag}#{id_}"
        else:
            tag_counters[tag] = tag_counters.get(tag, 0) + 1
            node_name = f"{tag}#{tag_counters[tag]}"
        item['_node_name'] = node_name
        node_names[node_name] = True

    # root と template ノードも追加
    node_names['root'] = True
    node_names['template'] = True

    # エッジリスト構築
    edges = []
    for item in docs:
        node_name = item.get('_node_name')
        parent = item.get('parent')
        if not node_name or not parent:
            continue
        parent_key = parent.lstrip('#')
        if parent_key in id_map:
            pnode = f"{id_map[parent_key]['tag']}#{parent_key}"
        else:
            pnode = parent_key
            node_names.setdefault(pnode, True)
        edges.append((pnode, node_name))

    # Mermaid 形式の文字列生成
    lines = ['```mermaid', 'graph TD']
    for name in node_names:
        lines.append(f'{name}["{name}"]')
    for p, c in edges:
        lines.append(f'{p} --> {c}')
    lines.append('```')
    return '\n'.join(lines)


def main():
    # 入力YAMLファイルをここで指定してください
    input_path = 'index.yaml'
    # 出力ファイルは入力ファイルと同じ階層・同じ名前の.md
    base = os.path.splitext(input_path)[0]
    output_path = f"{base}.md"

    mermaid_text = yaml_to_mermaid(input_path)
    # 出力ファイルに書き込む
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(mermaid_text)
    print(f"Mermaid図を{output_path}に出力しました。")

if __name__ == '__main__':
    main()
