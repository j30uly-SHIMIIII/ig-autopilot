# Claude Code プロンプト集:IG-AutoPilot(SMZ)

前提:リポジトリ直下に instagram_automation_requirements.md を置いた状態で、以下を順番に投げる。
各フェーズの動作確認が済んでから次を投げること。

---

## Phase 1:投稿基盤(ig_client + scheduler + carousel_gen)

```
instagram_automation_requirements.md を読んで、Phase 1(ig_client + scheduler + carousel_gen)を実装してください。

条件:
- Python 3.11、依存はrequirements.txtに集約
- リポジトリ構成は要件定義書の通り
- Graph APIはモッククライアントを用意し、実トークンなしで動作確認できること
- carousel_genは仮テンプレ(単色背景+Noto Sans JP)で日本語見出しを合成し、1080x1350のPNGを最大10枚出力
- 文字数超過時はフォントサイズ自動調整
- schedulerはSQLiteのqueueテーブルから当日分を取得し、config/account.yamlの時間帯に投稿(モックで検証)
- pytestで各モジュールの単体テストを付ける
- 完成したら動作確認手順をREADMEに書く

Phase 1が動くことを確認してから次フェーズに進みます。
```

## Phase 1.5:実トークン接続(手動工程完了後)

```
Meta側の設定が完了し、.envに実トークンを入れました。

- ig_clientを実APIに接続し、テスト用の非公開投稿(またはアーカイブ即時化)で1件投稿テストを実行する手順を作ってください
- レート制限(25投稿/24h)の残数チェック機能を追加
- トークン期限(60日)の残日数を確認するCLIコマンドを scripts/refresh_token.py に実装
- 失敗時のリトライ(3回、指数バックオフ)とログ出力を確認
```

## Phase 2:生成と分析(caption_gen + analytics)

```
Phase 2(caption_gen + insights_collector + report_gen)を実装してください。

条件:
- caption_genはOllama(.envのOLLAMA_HOST / OLLAMA_MODEL)でキャプション生成
- config/content_pillars.yaml のtone・ng_wordsを必ずプロンプトに組み込み、NG表現を含む出力は自動リジェクト→再生成(最大3回)→テンプレ文フォールバック
- Ollama接続不可時もテンプレ文で投稿を止めない
- insights_collectorは各投稿のreach / saves / shares / profile_visits / followsを日次取得しSQLiteへ保存(モック対応)
- report_genは週次で保存率ランキングと柱別パフォーマンスをCSV出力
- pytest追加、READMEに運用手順を追記
```

## Phase 3:企画自動化(content_planner)

```
Phase 3(trend_collector + content_planner)を実装してください。

条件:
- trend_collectorはconfig指定のRSSフィードから直近7日分を収集しSQLiteへ
- content_plannerはClaude API(model: claude-sonnet-4-6)を週1回呼び、翌週7日分の企画をJSON生成
- プロンプトには以下を含める:
  - content_pillars.yamlの3本柱と比率
  - report_genが出した直近の高パフォーマンス投稿の型
  - トレンド収集結果
  - ng_wordsリスト(出力への混入禁止)
- 出力JSONのスキーマバリデーションを実装し、不正時は1回だけ再生成
- 生成企画をメール送信し、48時間無返信なら自動採用とする承認フロー(notifier連携)を実装
- API呼び出しは週1回のみになるようcron設計と整合させる
```

## Phase 4:CS・導線・完全自動化(comment_responder + story_publisher)

```
Phase 4(comment_responder + story_publisher)を実装し、完全自動化を完成させてください。

条件:
- comment_responderは自投稿の新規コメントをキーワードマッチで定型返信
  - 返信は1コメント1回まで、1時間あたり上限件数をconfigで設定
  - マッチしないコメントは返信せずログのみ
- story_publisherは月水金にフィード投稿の再掲ストーリーズを投稿
- notifierを全モジュールに統合:投稿失敗・トークン期限14日前・例外発生をメール通知
- crontab.txtを最終版に更新し、VPSデプロイ手順(setup_vps.sh含む)をREADMEに完成させる
- 全体の統合テストを実行して結果を報告
```

## 運用開始後:調整用プロンプト例

```
# 投稿時間の最適化
report_genの結果を見ると19時より朝の保存率が高い。account.yamlの投稿時間を07:30に変更し、分析結果から最適時間帯を提案するロジックをreport_genに追加してください。

# テンプレ改善
carousel_genのデザインテンプレを差し替えたい。config/templates/に新しい背景PNGを置いたので、表紙・中面・最終面(CTA)の3種構成に対応させてください。

# 複数アカウント化(スケール時)
account.yamlを複数アカウント対応(accounts配列)にリファクタリングし、全モジュールがアカウントIDを引数に取る構造へ変更してください。
```
