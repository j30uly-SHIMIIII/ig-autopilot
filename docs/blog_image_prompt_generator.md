# ブログ・アイキャッチ用 AI画像生成プロンプト テンプレート

Midjourney / FLUX.1 などの画像生成AIに入力する、ブログ記事のアイキャッチ・サムネイル用プロンプトを作成するためのテンプレート。

## 使い方

1. 下記【入力】の3項目を記事に合わせて埋める。
2. 【生成プロンプト・テンプレート】のプレースホルダー（`{{ }}`）を置き換える。
3. 完成した英語プロンプトをそのままMidjourney / FLUX.1などに入力する。

## 入力

- 記事タイトル：`{{ARTICLE_TITLE}}`
- 記事のテーマ/概要：`{{ARTICLE_SUMMARY}}`
- 全体の雰囲気：`{{STYLE}}`（例：フラットイラスト風 / 3Dレンダリング風 / 実写シネマティック風 / ミニマル）

## 生成プロンプト・テンプレート

```
A professional, modern web blog header illustration in {{STYLE}} style, visually representing the theme of "{{ARTICLE_SUMMARY}}" (article title: "{{ARTICLE_TITLE}}"). Clean and sophisticated composition created by a professional web designer, intuitive visual metaphor that instantly conveys the article's topic at a glance, not overly abstract. Wide negative space with a soft, uncluttered background on one side (or centered) reserved for headline text overlay, clear visual hierarchy, balanced composition. Polished color palette, refined lighting, high-end editorial design, contemporary tech/media aesthetic, crisp details, no embedded text or typography in the image. --ar 16:9 --v 6 --style raw
```

## 記入例

条件：
- 記事タイトル：新NISAの始め方完全ガイド
- 記事のテーマ/概要：初心者向けに新NISAの制度としくみをやさしく解説する記事
- 全体の雰囲気：フラットイラスト風

生成プロンプト：

```
A professional, modern web blog header illustration in flat illustration style, visually representing the theme of "a beginner-friendly guide explaining Japan's new NISA investment tax-exemption system" (article title: "新NISAの始め方完全ガイド"). Clean and sophisticated composition created by a professional web designer, intuitive visual metaphor that instantly conveys the article's topic at a glance, not overly abstract: a growing plant sprouting from a coin stack beside a simplified piggy bank and upward trend line. Wide negative space with a soft, uncluttered background on the left side reserved for headline text overlay, clear visual hierarchy, balanced composition. Polished color palette in calming blues and greens, refined soft lighting, high-end editorial design, contemporary fintech/media aesthetic, crisp vector-style details, no embedded text or typography in the image. --ar 16:9 --v 6 --style raw
```

## 補足

- `--ar 16:9` はブログのアイキャッチ・サムネイル比率固定用。
- `--style raw`（Midjourney）は過度な演出を抑え、洗練されたWebデザイン寄りのトーンに寄せるために付与。FLUX.1など他ツールでは末尾のパラメータは適宜省略・調整する。
- テキストをAIに描画させず、後からデザインツール（Figma / Canva等）でタイトルを重ねる前提のため `no embedded text or typography in the image` を必ず含める。
