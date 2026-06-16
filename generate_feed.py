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

#記事の分類のために使っていいタグ一覧
ALLOWED_TAGS = [
    "AI",
    "セキュリティ",
    "ガジェット",
    "ビジネス",
    "開発",
    "科学",
    "その他",
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
    clean=re.sub("<[^>]*>", "", text)

    
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

            raw= clean_description(entry.get("summary", ""))

            #Claudeで要約とタグを一緒に取得
            analysis = analyze_with_claude(title, raw)

            new_articles.append({
                "title":title,
                "url":url,
                "source":feed_info["name"],
                "description":analysis["summary"],
                "tags":analysis["tags"]
            })

    return new_articles
                                                                                                                                                            
def collect_new_entries(known_urls):
    """
    RSSから、まだ持っていない記事だけを集める関数
    ここでは要約はしない(その分だけ速い)

    先に「全部で何件あるか」を知りたいから、要約とは分けて集めている
    進捗バーの「全○件中の○件目」を出すために使う
    返すのは {title,url,source,raw} の辞書のリスト
    """

    new_entries = []

    #登録されているサイトから一つずつ記事を集めていく
    for feed_info in RSS_FEEDS:
        print(f"取得中: {feed_info['name']} ...", flush=True)

        feed = feedparser.parse(feed_info["url"])

        for entry in feed.entries[:LIMIT_PER_FEED]:
            url = entry.get("link", "").strip()
            title = entry.get("title", "").strip()

            #URL・タイトルが無い、もう取得済みの記事なら飛ばす
            if not url or not title or url in known_urls:
                continue

            #調べた記事として覚えておく(同じものを2回入れないため)
            known_urls.add(url)

            raw = clean_description(entry.get("summary", ""))

            #まだ要約はしない。材料だけリストに溜めておく
            new_entries.append({
                "title": title,
                "url": url,
                "source": feed_info["name"],
                "raw": raw,
            })

    return new_entries


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

    subprocess.run(["git", "commit", "-m", f"記事を追加 {today}"], check=True)

    subprocess.run(["git", "push"], check=True)


def _parse_claude_json(text):
    """
    Claudeの出力から最初の {...}などが存在している場合は除去して、辞書形式にする
    if it can't oarse return None
    """

    #get rid of unwated json wraps
    text = text.replace("'''json", "").replace("''",(""))

    #最初と最後のwrapperの範囲飲み切り出す
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return None
    
    try:
        return json.loads(text[start:end +1])
    except json.JSONDecodeError:
        return None

def analyze_with_claude(title, raw_text):
    """
    claude に要約とタグ付けを一つのjsonとしてまとめる
    """

    #タグを文字列にしてpromptが読み込めるようにする
    tag_menu = ", ".join(ALLOWED_TAGS)

    #claudeへのpromptを渡す
    prompt = (
        "次のニュース記事を分析して、JSONのみ返してください。説明文はいらないです。\n"
        "形式: \n"
        "{'Summary': '日本で誰にでも端的に、わかりやすく要約'、'tags':['タグ1','タグ2']}\n\n"
        f"tags は以下の一覧から1~2個選ぶこと: {tag_menu}\n\n"
        f"タイトル: {title}\n\n本文 :{raw_text}"
    )

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=60, encoding="utf-8",    
        )

        if result.returncode == 0 and result.stdout.strip():
            data = _parse_claude_json(result.stdout)

            if data:
                #要約を取り出す
                summary= data.get("summary","").strip()

                #もし要約ができない場合は表示する
                if not summary:
                    summary= "Claudeの要約ができませんでした"

                #事前に用意したタグ以外ははじく
                tags=[]
                for t in data.get("tags", []):
                    if t in ALLOWED_TAGS:
                        #足しても問題ないタグを保管
                        tags.append(t)

                #タグが一つも当てはまらないなら"その他"にする
                return {"summary": summary, "tags":tags}

    except Exception as e:
        print(f"要約失敗 {title[:30]} : {e}")
    
    #ここで用悪失敗用のテキストとタグを返す
    return {"summary": summary, "tags":["その他"]}


#このファイルを直接実行したときに動くブロック
if __name__ == "__main__":

    index = load_index()

    #取得済みの全URLを set(重複なし)のURLのリストを追加していく
    known_urls = set()
    for entry in index:
        known_urls.add(entry["url"])

    # --- フェーズ1: 集めるだけ(速い)。これで全部で何件か分かる ---
    print("RSS feedから記事を取得します", flush=True)
    entries = collect_new_entries(known_urls)
    total = len(entries)

    #最初の合図。"PROGRESS 0 <総数>" を出して、Django側に総数を伝える
    print(f"PROGRESS 0 {total}", flush=True)

    if total == 0:
        print("新しい記事はありませんでした", flush=True)

    else:
        new_articles = []

        # --- フェーズ2: 1件ずつ要約＋タグ付け(遅い)。1件終わるごとに進捗を出す ---
        #enumerate(..., start=1) で i が 1,2,3... と数えてくれる
        for i, e in enumerate(entries, start=1):
            analysis = analyze_with_claude(e["title"], e["raw"])

            new_articles.append({
                "title": e["title"],
                "url": e["url"],
                "source": e["source"],
                "description": analysis["summary"],
                "tags": analysis["tags"],
            })

            #ここが大事:今 i 件目 / 全 total 件 終わった、とDjangoに知らせる
            print(f"PROGRESS {i} {total}", flush=True)

        #取得した記事を保存する
        saved = save_articles(new_articles, index)
        save_json(INDEX_FILE, index)
        print(f"{saved}件の記事を保存しました", flush=True)

        #GitHubに習得した記事をGithubにpushする
        print("GitHubにpush中", flush=True)
        psuh_to_github()
        print("完了! Githubのリポジトリを確認してください", flush=True)