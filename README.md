# IG-AutoPilot

マネー系Instagramアカウント「SMZ」を自動運用するためのシステム。詳細な要件は
[`instagram_automation_requirements.md`](./instagram_automation_requirements.md) を参照。

現在の実装状況: **Phase 1(投稿基盤: ig_client + scheduler + carousel_gen)完了**。
Graph APIは未接続でも `MockIGClient` により全機能をローカル検証可能。

## 動作環境

- Python 3.11 推奨(本番VPSはUbuntu 22.04+ / Python 3.11 を想定)
- ローカル検証は Python 3.9+ でも動作(型ヒントに `from __future__ import annotations` を使用し互換性を確保)

## セットアップ

```bash
cd ig-autopilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 実トークンは未設定でOK(Phase 1はモックモードで動作)
```

`config/templates/fonts/` に Noto Sans JP(Regular / Bold, OFL-1.1)を同梱済み。

## ディレクトリ構成(Phase 1時点)

```
config/
  account.yaml          # 投稿時間帯・レート制限・リトライ設定
  content_pillars.yaml  # 投稿3本柱・トーン・NGワード
  templates/fonts/       # Noto Sans JP
src/
  common/db.py           # SQLiteスキーマ(queue / posts)
  generator/carousel_gen.py  # カルーセル画像生成(Pillow)
  publisher/ig_client.py     # Graph APIラッパー + MockIGClient
  publisher/scheduler.py     # queueをポーリングして投稿
data/
  queue.db                # 実行時に自動生成されるSQLite本体
  generated/{date}/        # 生成された画像の出力先
tests/                    # pytest一式(19件)
```

## テスト実行

```bash
source .venv/bin/activate
python -m pytest -q
```

`pytest.ini` でリポジトリルートを `pythonpath` に追加済みのため、`pytest` 単体実行でも動作する。

## 動作確認手順(モックモードでの一連の流れ)

実トークンなしで「画像生成 → キュー投入 → 投稿」までを一通り確認できる。

```bash
source .venv/bin/activate
python - <<'PY'
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.common.db import connect
from src.generator.carousel_gen import generate_carousel

# 1. カルーセル画像を生成(2枚)
paths = generate_carousel(
    ["新NISAの仕組みをやさしく解説", "つみたて投資枠と成長投資枠の違い"],
)
print("generated:", paths)

# 2. queueテーブルに投稿予約を1件追加(1分後に投稿予定)
# scheduler は config/account.yaml の timezone(Asia/Tokyo)基準で比較するため、
# 実行環境のローカルTZに関わらずここでも明示的にAsia/Tokyoで計算する
scheduled_at = (datetime.now(ZoneInfo("Asia/Tokyo")) + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
with connect() as conn:
    conn.execute(
        """INSERT INTO queue (pillar_id, caption, hashtags, image_paths, scheduled_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("basics", "新NISAの基本をまとめました", "#NISA #新NISA #資産運用",
         json.dumps([str(p) for p in paths]), scheduled_at),
    )
print("queued for", scheduled_at)
PY
```

`scheduled_at` に到達したら scheduler を実行(cronの代わりに手動起動):

```bash
python -m src.publisher.scheduler
```

`IG_MOCK_MODE=true`(`.env` のデフォルト、または `IG_USER_ID`/`IG_ACCESS_TOKEN` 未設定時)では
`MockIGClient` が使われ、実際のInstagramには投稿されずSQLite上でstatusが `published` に更新される。
結果は以下で確認できる:

```bash
python -c "
from src.common.db import get_connection
conn = get_connection()
for row in conn.execute('SELECT id, status, ig_media_id, scheduled_at FROM queue'):
    print(dict(row))
"
```

## ForexFactory 赤(高インパクト)イベントのSlackアラート

`src/alerts/red_alert_scheduler.py` が ForexFactory の経済指標カレンダー
(公式ウィジェットが参照している公開JSONフィード)を定期的にポーリングし、
インパクトが「赤(High)」のイベント開始 `alert_minutes_before` 分前(デフォルト5分)に
Slack Incoming Webhook へ通知する。

```bash
source .venv/bin/activate
cp .env.example .env   # SLACK_WEBHOOK_URL に Slack Incoming Webhook URL を設定
python -m src.alerts.red_alert_scheduler
```

- 設定: `config/forexfactory.yaml`(タイムゾーン・アラート何分前・対象インパクト・通貨フィルタ・フィード元URL・キャッシュ有効期限)
- `SLACK_WEBHOOK_URL` が未設定の場合は `NullNotifier` となり、Slack送信は行わずログ出力のみ
- カレンダーフィードは `data/forexfactory_calendar_cache.json` に `cache_ttl_minutes`(デフォルト5分)キャッシュされる。
  毎分ポーリングのたびに毎回HTTP取得するとフィード側のレート制限(429 Too Many Requests)に当たるため
- 同一イベントへの重複アラートは `data/queue.db` の `calendar_alerts` テーブルで防止するため、
  アラート窓(`alert_minutes_before`)より短い間隔(例:毎分)でcron実行してよい

```
* * * * * cd /opt/ig-autopilot && python3 -m src.alerts.red_alert_scheduler
```

## 主要な設計判断

- **モック優先**: `create_ig_client()` は `IG_USER_ID` / `IG_ACCESS_TOKEN` が無い場合、自動的に
  `MockIGClient` を返す。実トークン接続はPhase 1.5で対応。
- **リトライ**: 投稿失敗時は `config/account.yaml` の `retry.max_attempts` まで指数バックオフで
  再試行し(`scheduled_at` を未来へ再設定)、上限到達で `status='failed'` として手動確認に回す。
- **カルーセル生成**: 見出しテキストは文字単位で折り返し(CJKには単語区切りがないため)、
  最大フォントサイズから安全領域に収まるまで段階的に縮小する。

## 次フェーズ

- Phase 1.5: 実トークン接続、レート制限残数チェック、リトライの実機検証
- Phase 2: `caption_gen`(ローカルLLM)+ `insights_collector` + `report_gen`
- Phase 3: `trend_collector` + `content_planner`(Claude API、週1回)
- Phase 4: `comment_responder` + `story_publisher` + 完全自動化

詳細な各フェーズの投げ方は [`claude_code_prompts.md`](./claude_code_prompts.md) を参照。
