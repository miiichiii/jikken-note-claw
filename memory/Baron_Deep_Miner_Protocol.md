# Deep GSEA Miner + Skeptic Review (Protocol)

## Mission
To identify "ironclad" pathogenic mechanisms in MCTO mice by exhaustively screening GSEA data, subjecting findings to rigorous skeptical review, and securing literature evidence.

## Inputs
- **Target**: `WT_vs_MCTO/tables/GSEA_by_LFC.tsv`
- **Reference**: `WT_vs_cKO/tables/GSEA_by_LFC.tsv`

## Execution Steps

### Step 1: Broad Mining (The Dragnet)
Identify all pathways that are:
- **Discordant**: Opposite direction in MCTO vs cKO.
- **Specific**: Strong in MCTO (|NES| > 1.8), silent in cKO.
- *No filtering by category at this stage.*

### Step 2: The Skeptic's Filter (The Crucible) 💀
Act as a harsh critic (Roland Baron persona). Attack each candidate:
- **"Just proliferation?"**: Is this just cell cycle/ribosome noise?
- **"Contamination?"**: Is this neural/muscle RNA from the bone marrow microenvironment?
- **"Artifact?"**: Is this a technical artifact of normalization?
- *Mark weak candidates as [REJECTED].*

### Step 3: The Librarian's Defense (The Evidence) 📚
For candidates that survive Step 2, perform a targeted literature search:
- **Query**: "Gene/Pathway X osteoclast phenotype knockout"
- **Requirement**: Find specific papers (Author, Year) linking the pathway to *bone resorption* or *fusion*.
- *If no paper exists, the candidate is marked [SPECULATIVE].*

### Step 4: Final Report (The Brief)
Compile the **"Baron-Ready List"**:
- **Mechanism**: The pathway/gene.
- **Data**: MCTO NES vs cKO NES.
- **Skeptic's Attack**: The likely objection.
- **Our Defense**: The logic + cited papers.

---
**Model Override**: Use `gpt-5.3-code` (via Codex) for execution to ensure high-reasoning capability.
