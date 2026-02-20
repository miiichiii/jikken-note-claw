# MCTO RNA-seq解析：現状整理と今後の進め方（引き継ぎ用）

## 1. 目的
- **MCTO（Mafb変異）で生じる骨溶解の分子機構**を、RNA-seqの**DEG/GSEA**から説明できる形にまとめる。
- **cKO（Mafb欠損）**との比較で、MCTO特異的な変化・逆転を抽出し、**Baron教授に説明可能な論理**を構築する。

---

## 2. データ
**フォルダ**
`/Users/michito/Library/CloudStorage/SynologyDrive-MCTO_paper/RNAseq data/byHamada/260124/`

**入力ファイル**
- `data/raw/Osteoclasts_WT vs lysm.xlsx` → **WT vs cKO**
- `data/raw/TAE_015_2group_N3_totalcount_quantile_normalized.xlsx` → **WT vs MCTO**

**解析パイプライン**
- `run_all.R` + `scripts/` (DESeq2/limma, GSEA, integration)
- 結果は `results/` に出力済み

---

## 3. 現在の進捗
### (A) DEG / GSEA の再整理
- **MCTO vs WT / cKO vs WT の分離比較で進める**（3群まとめは探索的には可能だが最終版では採用しない）
- cKO GSEAが空になっていたため、**gene_idをsymbolとして再計算済み**（`GSEA_by_LFC.tsv` 更新済）

### (B) 可視化（確定方針）
**最終版はB構成（分離比較）で作成**
- **MCTO vs WT**
  - z-score heatmap（WT左固定）
  - dot plot（WT左固定、正規化値）
- **cKO vs WT**
  - z-score heatmap（WT左固定）
  - dot plot（WT左固定、正規化値）
- **GSEAカテゴリ別図**
  - Lipid/Cholesterol
  - Immune/Inflammation
  - Mito/Metabolism
  - Adhesion/Fusion/ECM
  - pH/Acid response

---

## 4. 主要仮説（短期ゴール）
- **MCTOは単純なLoFではなく、炎症性・代謝破綻型の破骨細胞**
- **C1q / CD36 / Pf4 / Gpr65 / Lars2** などが候補だが、最終版では
  - **DEG上位20 + 指定遺伝子（計約26）** を用いて説明

---

## 5. 今後の作業フロー（ToDo）
### Step 1. 最終図表の確定
- **MCTO vs WT / cKO vs WT**の heatmap・dot plot を最終採用版として整理
- **GSEAカテゴリ別図**を最終採用版として整理

### Step 2. 結果の説明文（Baron教授向け）作成
- 各カテゴリごとに**leading edge遺伝子**を明示
- cKOとの逆転・MCTO特異的変化を強調

### Step 3. レポート統合
- 図表を差し込み
- 文章とセットで完成版を作成

---

## 6. 重要ファイルの場所
**図表（PDF）**
`/Users/michito/Library/CloudStorage/SynologyDrive-document/clawd/memory/visuals/`

**GSEAカテゴリ別**
- `WT_vs_MCTO_GSEA_*.pdf`
- `WT_vs_cKO_GSEA_*.pdf`

**3群まとめ（探索的）**
- `WT_cKO_MCTO_top27_heatmap_z.pdf`
- `WT_cKO_MCTO_top27_dotplot_z.pdf`

**Baron向けレポート**
- `memory/Baron_Defense_Report_v2.md`
- `memory/Baron_Defense_Report_v2_JP.docx`

---

## 7. 注意事項
- **cKO vs MCTO の直接比較はバッチ差の可能性あり** → 分離比較を推奨
- GSEAは**gene_symbol整備が重要**（cKOで空になっていた原因）

---

## 8. 次にやるべき具体アクション
1. **最終採用図の選定**（MCTO vs WT, cKO vs WT）
2. **GSEAカテゴリ図の整理**（不要カテゴリを削るか検討）
3. **Baron教授向け文章の統合**

---

（このファイルは引き継ぎ用に作成済み）
