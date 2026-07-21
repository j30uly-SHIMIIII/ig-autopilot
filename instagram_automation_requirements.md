# 要件定義書:Instagram自動運用システム「IG-AutoPilot」

## 0. プロジェクト概要

- 目的:マネー系Instagramアカウントを24時間自動運用し、国内証券・NISA口座開設アフィリエイトで収益化する
- 方針:Instagram Graph API(公式)のみ使用。自動フォロー/自動いいね等の規約違反機能は実装しない
- 稼働環境:VPS(Ubuntu 22.04以上想定、メモリ2GB〜)+ cron
- コスト方針:
  - 企画・戦略生成のみClaude API(1日1回バッチ、月数百円以内)
  - キャプション量産・定型文はローカルLLM(Ollama + Qwen2.5 7B等)またはテンプレート
  - 画像生成はPillowによるテンプレ合成を基本(外部生成APIは使わない)

## 1. リポジトリ構成

```
ig-autopilot/
├── README.md
├── .env.example              # 環境変数テンプレート
├── requirements.txt
├── config/
│   ├── account.yaml          # アカウント設定(投稿時間、頻度、トーン)
│   ├── templates/            # 画像テンプレート(背景、フォント指定)
│   │   ├── carousel_base.png
│   │   └── fonts/
│   └── content_pillars.yaml  # 投稿3本柱の定義とネタ比率
├── src/
│   ├── planner/
│   │   ├── trend_collector.py    # RSS/検索からネタ収集
│   │   └── content_planner.py    # Claude APIで週次企画生成
│   ├── generator/
│   │   ├── caption_gen.py        # ローカルLLMでキャプション生成
│   │   ├── carousel_gen.py       # Pillowでカルーセル画像生成
│   │   └── hashtag_gen.py        # ハッシュタグ選定(静的リスト+ローテーション)
│   ├── publisher/
│   │   ├── ig_client.py          # Graph APIラッパー
│   │   ├── scheduler.py          # 投稿キュー管理
│   │   └── story_publisher.py    # ストーリーズ投稿(導線用)
│   ├── engagement/
│   │   └── comment_responder.py  # コメントのキーワード自動返信
│   ├── analytics/
│   │   ├── insights_collector.py # インサイト日次取得
│   │   └── report_gen.py         # 週次レポート生成(Sheets or CSV)
│   └── common/
│       ├── db.py                 # SQLite(投稿キュー、実績、返信ログ)
│       ├── llm_local.py          # Ollamaクライアント
│       ├── llm_claude.py         # Claude APIクライアント
│       └── notifier.py           # 異常時通知(メール or LINE Notify代替)
├── data/
│   ├── queue.db                  # SQLite本体
│   └── generated/                # 生成済み画像・キャプション
├── scripts/
│   ├── setup_vps.sh              # 初期セットアップ
│   ├── refresh_token.py          # 長期トークン更新(60日毎)
│   └── manual_review.py          # 生成コンテンツの手動確認CLI
└── crontab.txt                   # cron設定一式
```

## 2. 各モジュール仕様

### 2.1 planner(企画部)— Claude API使用(唯一の従量課金箇所)

**trend_collector.py**
- 入力:config指定のRSSフィード(マネー系ニュース、日経、証券会社ブログ等)
- 処理:直近7日の記事タイトル+要約を収集、SQLiteに保存
- 実行:cron 毎日06:00

**content_planner.py**
- 入力:収集トレンド + content_pillars.yaml + 直近の投稿パフォーマンス(analytics連携)
- 処理:Claude API(claude-sonnet系)を1回呼び、翌週7日分の投稿企画をJSON生成
  - 各企画:タイトル / 3本柱の分類 / カルーセル各枚の見出しテキスト / CTA種別
  - プロンプトに「保存率の高かった過去投稿の型」を含め、勝ちパターンに寄せる
- 出力:queue.dbのplansテーブル
- 実行:cron 毎週日曜07:00(週1回のみ → API費最小化)

### 2.2 generator(制作部)— ローカルLLM + Pillow

**caption_gen.py**
- 入力:plansテーブルの企画
- 処理:Ollama(qwen2.5:7b想定)でキャプション生成。トーンはaccount.yamlで指定
- フォールバック:Ollama応答不良時はテンプレート文で代替(投稿を止めない)
- 実行:cron 毎日07:30(翌日分を前日生成)

**carousel_gen.py**
- 処理:テンプレPNG + 見出しテキストをPillowで合成、1080x1350を最大10枚生成
- 要件:日本語フォント埋め込み(Noto Sans JP)、文字数超過時の自動フォントサイズ調整
- 出力:data/generated/{date}/ 配下

**hashtag_gen.py**
- 静的リスト(ジャンル別30個×3セット)からローテーション選定。LLM不使用

### 2.3 publisher(投稿部)— Graph API

**ig_client.py**
- Instagram Graph API v21+ 対応
- 機能:カルーセル投稿(media container作成→publish)、ストーリーズ投稿、レート制限ハンドリング(25投稿/24h上限の管理)
- トークン:長期アクセストークンを.envで管理、refresh_token.pyで50日毎に自動更新

**scheduler.py**
- queue.dbから当日分を取得し、account.yaml指定の時間帯(例:07:00 / 19:00)に投稿
- 投稿成否をログ、失敗時はnotifierで通知+次回リトライ
- 実行:cron 5分毎に起動しキューをチェック(軽量ポーリング)

**story_publisher.py**
- 週3回、フィード投稿の再掲+リンクスタンプ相当の導線ストーリーズを投稿
- 実行:cron 月水金 20:00

### 2.4 engagement(CS部)

**comment_responder.py**
- 自投稿への新規コメントを取得し、キーワードマッチで定型返信(例:「詳細」→プロフリンク案内)
- 制約:返信は1コメント1回まで、1時間あたり上限を設けスパム判定を回避
- マッチしないコメントは返信せずログのみ(無理にLLM返信しない)
- 実行:cron 30分毎

### 2.5 analytics(分析部)

**insights_collector.py**
- 各投稿のreach / saves / shares / profile_visits / follows を日次取得しSQLiteへ
- 実行:cron 毎日23:30

**report_gen.py**
- 週次で保存率ランキング、CV導線クリック推定、伸びた型の集計をCSV出力(+任意でGoogle Sheets書き込み)
- content_planner.pyへのフィードバックデータを生成
- 実行:cron 毎週日曜06:30(planner実行前)

### 2.6 common

- db.py:SQLiteスキーマ管理(plans / queue / posts / insights / comments / logs)
- notifier.py:例外・投稿失敗・トークン期限接近をメール通知
- 全モジュール:構造化ログ(JSON lines)、例外時もプロセス全体を落とさない設計

## 3. cron設計(crontab.txt)

```
# 分 時 日 月 曜
*/5  *  * * *  python3 /opt/ig-autopilot/src/publisher/scheduler.py
*/30 *  * * *  python3 /opt/ig-autopilot/src/engagement/comment_responder.py
0    6  * * *  python3 /opt/ig-autopilot/src/planner/trend_collector.py
30   7  * * *  python3 /opt/ig-autopilot/src/generator/caption_gen.py && python3 /opt/ig-autopilot/src/generator/carousel_gen.py
0    20 * * 1,3,5  python3 /opt/ig-autopilot/src/publisher/story_publisher.py
30   23 * * *  python3 /opt/ig-autopilot/src/analytics/insights_collector.py
30   6  * * 0  python3 /opt/ig-autopilot/src/analytics/report_gen.py
0    7  * * 0  python3 /opt/ig-autopilot/src/planner/content_planner.py
0    3  * * *  python3 /opt/ig-autopilot/scripts/refresh_token.py --check
```

## 4. 環境変数(.env.example)

```
IG_USER_ID=
IG_ACCESS_TOKEN=            # 長期トークン
FB_APP_ID=
FB_APP_SECRET=
ANTHROPIC_API_KEY=          # planner専用
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
NOTIFY_EMAIL=
TZ=Asia/Singapore           # 投稿時間の基準TZ(日本向けならAsia/Tokyo)
```

## 5. 運用ルール・制約

1. Graph API公式機能のみ。フォロー/いいね/DM送信の自動化は実装禁止
2. アフィリリンクはインスタ内に直接貼らず、プロフィール→LP経由(アカウント保全)
3. 投稿内容に断定的な投資助言表現を含めない(「〜がおすすめ」ではなく情報提供型)。生成プロンプトに禁止表現リストを組み込む
4. 立ち上げ初月はmanual_review.pyで生成物を目視確認 → 品質安定後に完全自動へ移行
5. トークン失効・API仕様変更が最大の停止リスク → notifier通知を必ず監視

## 6. 実装フェーズ

- Phase 1:ig_client + scheduler + carousel_gen(手動企画で投稿が回る状態)
- Phase 2:caption_gen(ローカルLLM)+ analytics
- Phase 3:content_planner(Claude API)+ フィードバックループ
- Phase 4:comment_responder + story_publisher + 完全自動化

## 7. content_pillars.yaml(SMZアカウント確定版)

```yaml
account:
  brand: "SMZ"
  display_name: "SMZ|海外在住投資家"
  concept: "シンガポール在住投資家が日・星・比3拠点のリアルな資産運用を図解で発信"
  tone: "断定を避けた情報提供型。一人称は『私』。専門用語は1投稿1つまで、必ず平易な言い換えを添える"
  ng_words: ["絶対儲かる", "必ず", "元本保証", "おすすめの銘柄", "今すぐ買うべき"]

pillars:
  - id: basics          # 柱①リーチ獲得
    name: "お金の基礎図解"
    ratio: 0.4
    topics:
      - NISA/新NISAの仕組み
      - インデックス投資の基本
      - 複利・積立シミュレーション
      - 証券口座の選び方(→CV導線)
    cta: "保存して見返す / プロフィールから口座開設ガイドへ"

  - id: global          # 柱②差別化・保存狙い(SMZの独自領域)
    name: "海外在住投資家の視点"
    ratio: 0.4
    topics:
      - 東南アジア不動産市場レポート
      - ハワイ不動産のリアル
      - 米モーゲージ金利と不動産価格の関係
      - ゴールド投資(現物・ETF・積立の比較)
      - ロンドン/英不動産市場
      - 海外不動産投資の始め方と注意点
      - シンガポールの金融事情・税制の違い(一般情報の範囲)
    cta: "保存推奨 / フォローで海外投資情報を受け取る"

  - id: real            # 柱③信頼構築
    name: "実践と失敗談"
    ratio: 0.2
    topics:
      - 実際のポートフォリオ考察(数値はレンジ表記)
      - 過去の失敗と学び
      - 相場イベント時の考え方
    cta: "コメントで質問 / プロフィールへ"

posting:
  feed_per_day: 1
  feed_times: ["19:00"]      # JST基準、分析部の結果で自動調整可
  story_days: ["Mon", "Wed", "Fri"]
  story_time: "20:00"

monetization:
  primary: "国内証券・NISA口座開設アフィリエイト(A8/felmat等)"
  link_flow: "プロフィール → LP(口座開設ガイド) → ASPリンク"
  secondary_future: ["ゴールド積立系アフィリ", "自社レポート/講座(実績構築後)"]
```

## 8. Claude Codeへの指示例

```
このリポジトリ構成と要件定義に従い、Phase 1から順に実装してください。
- Python 3.11、依存は requirements.txt に集約
- 各モジュールに単体テスト(pytest)を付ける
- Graph APIはモッククライアントを用意し、実トークンなしでテスト可能にする
- まずPhase 1を完成させ、動作確認手順をREADMEに書いてから次フェーズへ
```
