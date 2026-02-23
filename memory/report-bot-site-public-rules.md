# Report Bot & site-public Rules

最終更新: 2026-02-18

## A. レポートボット運用ルール

### 1) 調査範囲・フィルタ
- **直近24時間 (newer_than:1d)** に公開された論文のみを対象とする。
- 新着がない場合は「新着なし」レポートを作成する。

### 2) 対象カテゴリ
- MAFB
- マクロファージと神経
- Natto Project

### 2) 実行スケジュール
- 定期実行（cron）: 毎週 月曜 09:00 (Asia/Tokyo)
- ジョブ名: `Weekly Research Project Reports (oss-120B)`

### 3) モデル
- サブエージェント専用: `lmstudio/gpt-oss-120b`
- リアルタイム会話では使用しない

### 4) 論文レポート必須項目（各論文）
- 論文タイトル (Title)
- 雑誌名 (Journal)
- インパクトファクター (Impact Factor)
- 公開日 (Date)
- 論文リンク (URL/DOI)

### 5) 記述方針
- 背景・手法・結果・結論を簡潔に記載
- MCTO等への示唆は「直接的に酷似する場合のみ」言及
- 該当論文なしの場合も必ず「新着なし」レポートを作成

### 6) 保存先
- `/Users/michito/Library/CloudStorage/SynologyDrive-document/clawd/site-public/reports/<CATEGORY>/YYYY-MM-DD.md`

### 7) GitHub反映・報告
- リポジトリ: `miiichiii/jikken-note-claw`
- ブランチ: `master`
- pushでVercelが自動デプロイ
- **報告ルール**: 完了報告時には必ず公開URL（https://site-public.vercel.app）を併記すること。

---

## B. site-public 運用ルール

### 1) 公開対象ディレクトリ
- `/Users/michito/Library/CloudStorage/SynologyDrive-document/clawd/site-public`
- 公開に必要なファイルのみを置く（作業用/個人用ファイルは置かない）

### 2) 主要ファイル
- `site-public/index.html`（カードUIトップ）
- `site-public/robots.txt`
- `site-public/vercel.json`
- `site-public/middleware.js`（Basic認証）
- `site-public/reports/...`（カテゴリ別レポート）

### 3) セキュリティ・公開ポリシー
- Vercel Basic認証を有効化（`BASIC_AUTH_USER`, `BASIC_AUTH_PASS`）
- 検索エンジン対策:
  - `robots.txt` でクロール拒否
  - `meta noindex,nofollow`
  - `X-Robots-Tag: noindex, nofollow`

### 4) デプロイ方針
- 原則: GitHub `master` への push で自動反映
- 手動反映が必要なときのみ:
  - `cd .../site-public && npx -y vercel --prod`

### 5) デザイン方針
- モダンなカードUI
- 研究カテゴリをカードとして配置し、各カテゴリレポートへリンク

---

## C. 変更時の原則
- ルール変更はこのファイルへ追記・更新する
- カテゴリ変更時は以下を同時更新する:
  1. `site-public/index.html`
  2. `site-public/reports/<CATEGORY>/`
  3. レポート生成プロトコル（`memory/research_report_protocol.md`）
  4. cronジョブのプロンプト
