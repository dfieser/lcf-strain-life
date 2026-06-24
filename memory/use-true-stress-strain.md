---
name: use-true-stress-strain
description: All LCF analysis must use true stress-strain, not engineering
metadata:
  type: feedback
---

All LCF analysis in this project must use TRUE stress and TRUE strain curves, not engineering stress-strain.

**Why:** True values correctly represent material response under the large plastic strains typical of low cycle fatigue; engineering values misstate stress/strain once cross-section changes.

**How to apply:** Convert any engineering-referenced input at ingestion: ε_true = ln(1 + ε_eng), σ_true = σ_eng·(1 + ε_eng). See [[project-scope-lcf-automation]].
