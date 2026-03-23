# Source vs Git Delta Report

Date: 2026-03-23
Scope: comparison between the uploaded project source set available in the working context and the repository state built through PR #1 plus this PR #2 branch.

## Purpose

This report records what is already represented in Git, what is only summarized, what has a repo-native export, and what still exists only in the uploaded source set.

## Delta status legend

- **Exact / near-exact**: substantive text preserved with little or no normalization.
- **Repo-native export**: substantive text imported into Git, but formatting/layout fidelity is reduced.
- **Source-note only**: Git contains only a catalog entry or short source note, not the full document body.
- **Missing in Git**: source exists in the uploaded set but no meaningful in-repo body has been added yet.

## Document-by-document status

| Source document | Git status after PR #1 + PR #2 branch | Delta summary |
| --- | --- | --- |
| `adaptive_advertising_software_selection_directive.txt` | Exact / near-exact | Already imported as a full text file in PR #1 |
| `Adaptive_Retail_Golden_Roadmap_V2.docx` | Source-note only | Git currently has a roadmap anchor note, not the full body |
| `System Architecture Document for a Privacy-First Edge CV Ad Platform on Jetson.pdf` | Source-note only | Git currently has an architecture anchor note, not the full body |
| `Consolidated Interface Control Document v1.0 for DeepStream, FastAPI, and React.pdf` | Missing in Git | No repo-native contract body yet |
| `adaptive_retail_interface_addendum_v1_0.pdf` | Missing in Git | No repo-native addendum body yet |
| `Technical Requirements Package for a Privacy-First CV-Driven Adaptive Display Edge Appliance.pdf` | Missing in Git | No repo-native requirements body yet |
| `Adaptive_Retail_Advertising_VV_Plan.pdf` | Missing in Git | No repo-native V&V body yet |
| `Pilot_Validation_Protocol_v1_0.docx` | Repo-native export | Exported into Git as markdown-like text with simple tables |
| `Adaptive_Retail_Coding_AI_Governance_Charter_v1_0.docx` | Missing in Git | Planned next, but not yet committed on this branch |
| `Adaptive_Retail_Target_End_State_Vision_v1_0.txt` | Missing in Git | Useful supporting context, not yet copied into repo |
| `Adaptive_Retail_Storage_Retention_and_Eviction_Guidance_v1_0.txt` | Repo-native export | Imported as a guiding text document |
| `Adaptive_Retail_Design_Rationale_and_Implementation_Notes_v1_1.txt` | Missing in Git | Supporting rationale not yet copied into repo |
| `Adaptive_Retail_CSI_Rebaseline_CRM_Delta_Pack_v1_1.txt` | Missing in Git | Change-control context not yet copied into repo |
| `Adaptive_Retail_System_Development_Snapshot_v1_0.md` | Exact / near-exact | Imported in PR #1 as a living artifact |
| `Adaptive_Retail_Change_Resolution_Matrix_v1_0.md` | Missing in Git | Living governance artifact not yet copied into repo |

## Structural deltas already resolved by PR #1

PR #1 resolved the repository-organization gap by adding:
- document authority separation
- source-to-repository mapping
- authoritative/supporting/living catalogs
- initial baseline anchors for roadmap and architecture

## Fidelity notes

### DOCX exports

DOCX-to-markdown exports preserve headings, paragraphs, and simple tables, but lose some Word-specific semantics such as section layout, advanced table formatting, and any hidden document metadata.

### PDF exports

PDF-to-text exports preserve searchable body content but lose exact pagination fidelity, visual layout, figure placement, and some table geometry. For implementation grounding this is usually acceptable; for formal publishing the original PDF remains the authoritative visual source.

## What remains different between source and Git right now

1. Git is still incomplete for the large PDF-controlled baseline set.
2. Some Git files are source notes rather than full document bodies.
3. Several supporting and living artifacts still exist only in the uploaded working set.
4. Repo-native exports trade fidelity for searchability and AI-grounding convenience.

## Recommended next import order

1. Consolidated ICD v1.0
2. Technical Requirements Package
3. Verification and Validation Plan
4. Golden Roadmap V2
5. System Architecture Document
6. Interface Addendum v1.0
7. Coding AI Governance Charter v1.0
8. Change Resolution Matrix and remaining supporting texts

## Current conclusion

The repository now has a usable document-control structure and a partial repo-native body set, but it does not yet contain the full authoritative corpus in searchable in-repo form. The largest remaining gap is the PDF-controlled baseline set.