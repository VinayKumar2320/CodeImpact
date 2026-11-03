# Historical Dataset Collection & Labeling Methodology

## 1. Overview
The CodeImpact dataset collection pipeline mines pull requests, commit metadata, AST syntactical differences, and post-merge defect signals across open-source repositories to build a rigorously grounded training dataset without synthetic hallucinations.

The reference dataset includes **1,200 pull request records** mined across four major repositories:
- `tiangolo/fastapi`
- `psf/requests`
- `encode/httpx`
- `pallets/flask` (used exclusively as an out-of-domain cross-repository evaluation holdout)

---

## 2. Temporal Splitting & Zero Look-Ahead Leakage Guarantee

To prevent temporal data leakage (where future codebase states or defect frequencies leak into past training iterations), all dataset splits are constructed chronologically per repository:

$$t_{\text{train}}^{\max} < t_{\text{val}}^{\min} \le t_{\text{val}}^{\max} < t_{\text{test}}^{\min}$$

```
Repository Timeline (per-repo commit history):
[==== TRAIN (70%) ====] ---> [== VAL (15%) ==] ---> [== TEST (15%) ==]
t_0                     t_1                  t_2                 t_3
```

- **Validation Function**: `DatasetLoader.validate_temporal_splits(train, val, test)` verifies that:
  - $\max(\text{created\_at}_{\text{train}}) < \min(\text{created\_at}_{\text{val}})$
  - $\max(\text{created\_at}_{\text{val}}) < \min(\text{created\_at}_{\text{test}})$
- **Holdout Set (`datasets/cross_repo_test.jsonl`)**: Mined from `pallets/flask` with zero overlap with the training repositories to empirically measure generalizability on unseen architectures.

---

## 3. Ground Truth Labeling Definitions

Each pull request $PR_i$ is labeled with a binary regression indicator $y_i \in \{0, 1\}$ using two validated signals:

### Tier 1 Defect Labeling (High Confidence)
A post-merge regression is recorded ($y_i = 1$) if within 30 days of merging $PR_i$:
1. A subsequent commit explicitly references the PR with fix keywords:
   - `fix(es)? #<PR_NUMBER>`, `closes? #<PR_NUMBER>`, `reverts? #<PR_NUMBER>`, or `regression from #<PR_NUMBER>`.
2. A direct `git revert` commit was executed targeting the PR's merge commit SHA.
3. A subsequent bug-fix commit modifies $>50\%$ of the lines or functions introduced by $PR_i$.

### Tier 2 Defect Labeling (Moderate Confidence)
If no explicit issue reference is found, Tier 2 heuristics flag potential regressions if:
1. A patch release tag (e.g. `v1.2.1` following `v1.2.0`) was released within 7 days containing fixes to the modified modules.
2. The author or reviewer opened an urgent hotfix PR touching the exact same files within 14 days.

---

## 4. Dataset Splits Breakdown

| Split Name | File Path | Record Count | Positives (Defects) | Prevalence | Repositories |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Train** | `datasets/train.jsonl` | 630 | 99 | 15.71% | `fastapi`, `requests`, `httpx` |
| **Validation** | `datasets/val.jsonl` | 135 | 18 | 13.33% | `fastapi`, `requests`, `httpx` |
| **In-Domain Test** | `datasets/test.jsonl` | 135 | 23 | 17.04% | `fastapi`, `requests`, `httpx` |
| **Cross-Repo Test**| `datasets/cross_repo_test.jsonl` | 300 | 45 | 15.00% | `pallets/flask` (Holdout) |
| **Total** | `datasets/manifest.json` | **1,200** | **185** | **15.42%** | **4 Repositories** |

---

## 5. Dataset Reproduction Command

To reproduce the dataset extraction:
```bash
python scripts/collect_dataset.py \
  --output-dir datasets/ \
  --repos tiangolo/fastapi psf/requests encode/httpx pallets/flask \
  --limit-per-repo 300
```
Validation manifests and checksums are stored at `datasets/manifest.json`.
