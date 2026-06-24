---
name: project-scope-lcf-automation
description: What the Low Cycle Fatigue MCP project is and is not trying to do
metadata:
  type: project
---

This project builds an AI-agent-friendly automated resource (MCP server) for Low Cycle Fatigue (LCF) analysis in materials science. Goal: let any scientist feed in their own LCF test data and get standard reduced quantities, fitted parameters, and plots.

The source manuscript (CoNiV alloy study) is used ONLY as a specification of the analysis pipeline — we are NOT replicating its material-specific context, comparison alloys, or phenomena like serrations/PLC effect. Analysis pipeline and equations documented in docs/reference/. Data-flow and compute/recall design in docs/design/WORKFLOW.md. See [[use-true-stress-strain]].
