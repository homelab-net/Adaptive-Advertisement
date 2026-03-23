# Source vs Git Delta Report — PR3 Status

Date: 2026-03-23
Scope: comparison between the uploaded project source set and the repository state after PR #1, PR #2, and this PR #3 branch.

## Status legend

- **Exact / near-exact**: substantive text preserved with little or no normalization.
- **Repo-native export**: substantive text imported into Git, but PDF or DOCX formatting/layout fidelity is reduced.
- **Curated repo-native digest**: a structured in-repo summary captures the governing substance, intent, and implementation implications, but not every line of source text.
- **Source-note also present**: a shorter anchor/catalog file still exists from prior PRs in addition to a fuller export or digest.
- **Still missing in Git**: source exists in the uploaded set but no meaningful in-repo body has been added yet.

## Document-by-document status

| Source document | Git status after PR #3 branch | Delta summary |
| --- | --- | --- |
| `adaptive_advertising_software_selection_directive.txt` | Exact / near-exact | Full text imported in PR #1 |
| `Adaptive_Retail_Golden_Roadmap_V2.docx` | Source-note only | Roadmap anchor note exists in Git; full body not yet imported |
| `System Architecture Document for a Privacy-First Edge CV Ad Platform on Jetson.pdf` | Source-note only | Architecture anchor note exists in Git; full body not yet imported |
| `Consolidated Interface Control Document v1.0 for DeepStream, FastAPI, and React.pdf` | Missing in Git | No full in-repo body yet |
| `adaptive_retail_interface_addendum_v1_0.pdf` | Missing in Git | No full in-repo body yet |
| `Technical Requirements Package for a Privacy-First CV-Driven Adaptive Display Edge Appliance.pdf` | Missing in Git | No full in-repo body yet |
| `Adaptive_Retail_Advertising_VV_Plan.pdf` | Missing in Git | No full in-repo body yet |
| `Pilot_Validation_Protocol_v1_0.docx` | Repo-native export | Export added in PR #2 |
| `Adaptive_Retail_Coding_AI_Governance_Charter_v1_0.docx` | Missing in Git | Not yet imported as full text body |
| `Adaptive_Retail_Target_End_State_Vision_v1_0.txt` | Curated repo-native digest | Long-term design intent now represented in Git as structured digest |
| `Adaptive_Retail_Storage_Retention_and_Eviction_Guidance_v1_0.txt` | Repo-native export | Text copy added in PR #2 |
| `Adaptive_Retail_Design_Rationale_and_Implementation_Notes_v1_1.txt` | Curated repo-native digest | Key rationale, deployment, privacy, and support implications now represented in Git |
| `Adaptive_Retail_CSI_Rebaseline_CRM_Delta_Pack_v1_1.txt` | Curated repo-native digest | Change-control implications and re-baseline requirements now represented in Git |
| `Adaptive_Retail_System_Development_Snapshot_v1_0.md` | Exact / near-exact | Imported in PR #1 as a living artifact |
| `Adaptive_Retail_Change_Resolution_Matrix_v1_0.md` | Exact / near-exact | Repo-native markdown copy added in PR #3 |

## What PR #3 improved

PR #3 closes part of the remaining gap by adding:
- a repo-native living copy of the change resolution matrix
- a curated digest of the target end-state vision
- a curated digest of the design rationale and implementation notes
- a curated digest of the CSI camera rebaseline CRM delta pack

## Remaining deltas

1. The biggest remaining gap is still the authoritative PDF corpus and the full roadmap/governance body.
2. Some supporting documents are represented as curated digests rather than line-for-line copies.
3. The repo now has better searchable coverage for future architecture and change-control decisions, even though it does not yet hold the complete authoritative corpus in repo-native form.

## Recommended next import order

1. Consolidated ICD v1.0
2. Technical Requirements Package
3. Verification and Validation Plan
4. Golden Roadmap V2
5. System Architecture Document
6. Interface Addendum v1.0
7. Coding AI Governance Charter v1.0

## Conclusion

The repository now has a stronger document-control structure, a partial repo-native corpus, and much better coverage of supporting rationale and change-control context. The principal remaining gap is still the searchable in-repo body of the authoritative contract, requirements, verification, roadmap, architecture, and governance documents.