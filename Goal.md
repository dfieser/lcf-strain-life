# Project Overview

We're building an **automated, AI-agent-friendly tool for low cycle fatigue (LCF) analysis**. A scientist drops in their own test data, and the tool runs the full standard analysis automatically.

## The problem

Low cycle fatigue is what happens when a material is repeatedly pushed hard enough to bend slightly each time, until it eventually cracks — the kind of wear seen in turbine blades, pressure vessels, and engine parts. Analyzing it is a well-established but tedious process: labs do the same calculations by hand or in one-off spreadsheets, which is slow and easy to get wrong.

## What we're building

A tool that takes raw LCF test data and automatically:

- Cleans and standardizes it (using true stress–strain).
- Measures energy absorbed per loading cycle.
- Tracks how the material hardens and softens over its life.
- Fits the standard fatigue models (Coffin-Manson, Basquin, Ramberg–Osgood) and predicts fatigue life.

Because it's built to be called by an AI agent, the whole analysis can be run conversationally — no re-deriving the procedure each time.

## Why it matters

It turns a slow, error-prone manual workflow into something **any scientist can reproduce with their own data** in minutes. The tool is general-purpose and material-agnostic.
