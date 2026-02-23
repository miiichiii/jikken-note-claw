# AI Team Organization: Mission Control

センセイ（濱田教授）の研究と業務を支えるデジタル組織の構成図です。

## 1. 統括 (Chief Orchestrator)
- **エージェント名**: macstudio-bot
- **担当モデル**: Gemini 3 Pro / Flash
- **責任**: センセイとの対話、全サブエージェントの指揮・監督、長期記憶の管理、意思決定。

## 2. 開発・デザイン部門 (Development & Design)
- **UI/UX デザイナー (Designer)**:
    - **モデル**: Gemini 3 Pro
    - **責任**: Mission Control の視覚的デザイン、Tailwind CSS/Glassmorphism の適用、ユーザー体験の向上。
- **フロントエンド開発者 (Developer)**:
    - **モデル**: Gemini 3 Pro
    - **責任**: HTML/JavaScript の実装、動的データ（JSON）との連携、新規機能のコーディング。
- **システム・レビューワー (Reviewer/Critic)**:
    - **モデル**: Gemini 3 Flash
    - **責任**: コードの品質チェック、セキュリティ監査、エラー検出、デプロイ前の最終承認。

## 3. 研究・執筆部門 (Research & Content)
- **サイエンティフィック・ライター (Writer)**:
    - **モデル**: DeepSeek-R1-70B (Local)
    - **責任**: 論文の内容要約、研究レポートの執筆、学術的背景の解説。
- **データ・アナリスト (Analyst)**:
    - **モデル**: DeepSeek-R1-70B (Local)
    - **責任**: 研究戦略DB（CSV）の更新、最新論文の自動スキャニング、データ整合性の維持。

## 4. 事務・運用部門 (Operations)
- **メール事務官 (Email Clerk)**:
    - **モデル**: GPT-OSS 20B (Local) + Gemini (Cloud)
    - **責任**: Gmail の監視・重要度選別、要約の作成、メール返信案の起案。
- **メモリー・アーカイブ係 (Archivist)**:
    - **モデル**: Gemini 3 Flash
    - **責任**: `memory/` フォルダの整理、定期的な記憶のメンテナンス、重複情報の削除。
