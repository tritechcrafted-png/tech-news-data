import json
import os
import re
import subprocess
from datetime import date

import feedparser

#取得する記事のソースを辞書形式で保管
RSS_FEEDS=[
    {"name":"Hacker News", "url": "https://news.ycombinator.com/rss"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "The Verge Tech", "url":"https://www.theverge.com/tech/rss/index.xml"},
    {"name": "Ars technica", "url":"https://feeds.arstechnica.com/arstechnica/technology-lab"},
    {"name": "MIT Tech Review", "url":"https://www.technologyreview.com/feed/"},
]

INDEX_FILE="index.json"

#書くサイトごとに最大いくつの記事を取得するのか
LIMIT_PER_FEED=20

def clean_description(text):
    """
    RSSからHTMLタグなどを除去して記事の内容のみ入手
    """

    #テキストが何もないなら何も返さない
    if not text:
        return ""
    
    #指定したものに一致するものを置き換える

    #re.sub(置き換える対象、置き換えるもの、置き換える全体のテキスト)
    #<[^>]>: HTMLタグにある表現一覧
    clean=re.sub("<[^>]>", "", text)

    
    #r'\s':は一つ以上の空欄を指定する
    #一つ以上の空欄を一つの空欄に置き換える
    clean=re.sub(r"\s+", " ", clean)

    return clean.strip()

def load_index():
    """
    index.jsonを読み込んでリストで返す
    ファイルがまだ存在しない場合は空リストを返す
    """

    try:
        #読み込み権限でINDEX_FILEを読み込ませる
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    
def save_json(filepath, data):
    """
    PythhonのobjectをきれいにしたJSONファイルとして書き出す
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_new_articles(known_urls):
    """
    全mRSSフィードから記事を入手して、known_urlsにないものだけリストで返す
    """

    new_articles = []

    #登録されているURLから一つずつ記事を入手していく
    for feed_info in RSS_FEEDS:
        print(f"習得中: {feed_info['name']}.....")

        #feedparser.parse():  HTTPリクエストとXMLのデータの仕分け(暗号の解読に近い)ことをしてくれる
        feed=feedparser.parse(feed_info["url"])

        for entry in feed.entries[:LIMIT_PER_FEED]:

            url = entry.get("link", "").strip()

            title=entry.get("title", "").strip()

            #URL,タイトル、取得済みの記事なら飛ばす
            if not url or not title or url in known_urls:
                continue

            #もうすでに調べた記事ならリストに追加する
            known_urls.add(url)

            new_articles.append({
                "title":title,
                "url":url,
                "source":feed_info["name"],
                "description":clean_description(entry.get("summary", ""))
            })

    return new_articles
                                                                                                                                                            
def save_articles(new_articles, index):
    """
    新しい記事をひとつづつ　jsonファイルとして保存
    indexに記事の名前を保管して、記事の数を保管する
    """

    #isoformat():日付をと整えて、ファイル名として保管する
    today= date.today().isoformat()

    #その日付のフォルダのパスを決定
    folder=f"articles/{today}"

    #実際にフォルダを作成する
    os.makedirs(folder, exist_ok=True)

    count=0

    for e in index:
        #もし、すでに今日の日付のフォルダが保存されているなら
        if f"/{today}/" in e["path"]:
            #もしパスにすでに今日の日付フォルダが含まれているなら、一つの記事が存在していることになる
            count +=1

    #今日の記事フォルダに何件存在しているのか数える
    for article in new_articles:
        count+=1

        #記事を番号付きにして、2重付けなどを防ぐ
        #{count:03}=3桁ゼロ埋めにする　1なら001みたいな感じで
        path=f"articles/{today}/{count:03}.json"

        #jsonファイルを保存する
        save_json(path, article)

        index.append({"path":path, "url": article["url"]})

    #何件の記事があるのか返す
    return len(new_articles) 

def psuh_to_github():
    """
    新しい記事とindex.jsonの変更をGithubにpushする
    """

    #今日の日付を得る
    today=date.today().isoformat()
    
    #subprocessでPythonからターミナルコマンドを実行されるコマンド
    #check = True でコマンドが失敗したら、エラーを出す
    subprocess.run(["git", "add", "."], check=True)

    subprocess.run(["git", "commit", ""])

    subprocess.run(["git", "push"], check=True)

#このファイルを直接実行したときに動くブロック
if __name__ == "__main__":
    
    #
    index=load_index()

    #取得済みの全URLを set(重複なし)のURLのリストを追加していく
    known_urls = set()

    #
    for entry in index:
        known_urls.add(entry["url"])

    #新しい記事を習得する
    print("RSS feedから記事を習得する")
    new_articles=fetch_new_articles(known_urls)

    #もし、新しい記事がない場合
    if not new_articles:
        print("新しい記事はありませんでした")

    #新しい記事がある場合は
    else:
        #取得した記事を保存する
        saved=save_articles(new_articles, index)
        save_json(INDEX_FILE, index)

        print(f"{saved}件の記事を保存しました")

        #GitHubに習得した記事をGithubにpushする
        print("GitHubにpush中")
        psuh_to_github()
        print("完了! Githubのリポジトリを確認してください")