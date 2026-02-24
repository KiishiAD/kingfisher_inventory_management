# Mermaid and Preview Guide

This page explains how to read documentation diagrams in this repository.

## Core rule used in this guide
Every Mermaid diagram is paired with a plain-text fallback.
If Mermaid fails to render in your editor, read the fallback directly below the diagram.

## VS Code preview tips
1. Open a `.md` file.
2. Run **Markdown: Open Preview**.
3. If Mermaid still does not appear, use **Markdown: Open Preview to the Side** and reload window.
4. If the extension stack still fails, use the text fallback blocks.

## Why the docs are still readable without Mermaid
The explanation is written in plain English first.
Diagrams are reinforcement, not the only source of meaning.

## Minimal Mermaid patterns used here
- `flowchart TD` for process flow
- `sequenceDiagram` for actor interactions
- `erDiagram` for model relationships

## Text fallback example
```text
User submits requisition
  -> approver decides
  -> system creates PO or issues stock
```

## Where in code
- Workflow source logic: `supplychain_test/supplychain/views/requisition_views.py::RequisitionDetailView`
- ER source models: `supplychain_test/supplychain/models/__init__.py::__all__`
- Template rendering path: `supplychain_test/supplychain_test/settings/base.py::TEMPLATES`
