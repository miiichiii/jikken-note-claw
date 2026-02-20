# 2026-02-20 MCTO 骨髄FCM解析 & コロニーアッセイ

## 目的
1. MCTOマウス骨髄におけるマクロファージ系プロジェニター（MDP/cMoP等）のFCM解析。
2. M-CSFコロニーアッセイによる増殖能の再確認。

## 方法 (1) FACS
- **サンプル**: 骨髄 (Bone Marrow) 7検体 (Ctrl n=4, MCTO n=3)
- **解析手法**: FACS (Flow Cytometry)

### 抗体パネル (確定)
- **Dump (Lineage)**: PE
  - CD3, B220, Ter119, Gr-1
- **Stem/Progenitor**:
  - **Sca-1**: PerCP-Cy5.5
  - **CD117 (c-Kit)**: PE-Cy7
- **Macrophage Lineage**:
  - **CD115 (M-CSFR)**: APC

### 染色・測定準備 (Staining & Prep)
- **Wash**: 完了
- **DAPI染色 (Live/Dead)**:
  - バッファー: 4% FBS/PBS
  - 希釈: 1/3000 (DAPI 2 µL / Buffer 6 mL)
  - 分注: 500 µL/tube (Sample×7 + Control×1)
- **ステータス**: 測定準備完了 (Ready for FACS)

## 測定ログ (Instrument Settings)
- **Voltage調整**:
  - **APC (CD115)**: シグナル微弱のため、Voltageを上げて調整。
  - **その他**: 変更なし（Default/維持）。
  - ヒストグラムでSaturation（振り切れ）がないことを確認済み。
- **特記事項**:
  - Voltage調整後、以降の測定は学生に引き継ぎ。
  - センセイは県立医療大へ移動。

## 方法 (2) コロニーアッセイ
- **培地調製**:
  - Total: 8 mL
  - M-CSF (10 ng/µL stock): **80 µL** (Final 100 ng/mL)
  - Penicillin/Streptomycin (100x): **80 µL** (1/100)
- **播種**:
  - 密度: 1×10^4 cells / well
  - 手順: 10倍希釈液から微量を分取
- **ステータス**: 播種完了 (Maki-owatta)

## 結果
### 骨髄細胞数 (濃度: cells/ml)
**Control (MCTO/GFP)**
- 1: 1.2 × 10^7 /ml
- 2: 1.5 × 10^7 /ml
- 3: 1.3 × 10^7 /ml
- 4: 1.0 × 10^7 /ml
**(平均: 1.25 × 10^7 /ml)**

**MCTO**
- 1: 4.5 × 10^6 /ml
- 2: 8.9 × 10^6 /ml
- 3: 6.1 × 10^6 /ml
**(平均: 6.5 × 10^6 /ml)**

### 気づき
- MCTO群の骨髄細胞濃度（/ml）は、Control群と比較して減少傾向にある（平均値で約半分）。

## 考察
- CD115+ CD117+ 分画の変動に注目。
