# Source vs Git Delta Report — PR4 Status

Date: 2026-03-23
Scope: comparison between the uploaded project source set and the repository state after PR #1 through PR #4.

## Status legend

- **Exact / near-exact**: substantive text preserved with little or no normalization.
- **Repo-native export**: substantial text imported from source with reduced layout fidelity.
- **Curated authoritative extract**: structured in-repo extract that captures governing substance, acceptance logic, interfaces, and implementation implications, but not every line of source text.
- **Curated supporting digest**: structured in-repo digest for supporting/change-control material.
- **Source-note only**: Git contains only an anchor/catalog note, not a substantive in-repo body.
- **Still missing in Git**: source exists in the uploaded set but no meaningful in-repo body has been added yet.

## Document-by-document status

| Source document | Git status after PR #4 branch | Delta summary |
| --- | --- | --- |
| `adaptive_advertising_software_selection_directive.txt` | Exact / near-exact | Full text imported in PR #1 |
| `Adaptive_Retail_Golden_Roadmap_V2.docx` | Curated authoritative extract + source note | Active roadmap substance now represented in repo; not line-for-line full export |
| `System Architecture Document for a Privacy-First Edge CV Ad Platform on Jetson.pdf` | Curated authoritative extract + source note | Architectural boundaries and implications now represented in repo |
| `Consolidated Interface Control Document v1.0 for DeepStream, FastAPI, and React.pdf` | Curated authoritative extract | Core ICD-1 through ICD-4 contract surface now represented in repo |
| `adaptive_retail_interface_addendum_v1_0.pdf` | Curated authoritative extract | ICD-5 through ICD-8 and ICD-NET-1 role and implications now represented in repo |
| `Technical Requirements Package for a Privacy-First CV-Driven Adaptive Display Edge Appliance.pdf` | Curated authoritative extract | Measurable completion and acceptance baseline now represented in repo |
| `Adaptive_Retail_Advertising_VV_Plan.pdf` | Curated authoritative extract + earlier repo-native export | V&V gate logic and evidence posture now represented in stronger form |
| `Pilot_Validation_Protocol_v1_0.docx` | Repo-native export | Export added in PR #2 |
| `Adaptive_Retail_Coding_AI_Governance_Charter_v1_0.docx` | Curated authoritative extract | Governance rules for AI-assisted implementation now represented in repo |
| `Adaptive_Retail_Target_End_State_Vision_v1_0.txt` | Curated supporting digest | Long-term design intent represented in repo |
| `Adaptive_Retail_Storage_Retention_and_Eviction_Guidance_v1_0.txt` | Repo-native export | Guiding implementation text imported in PR #2 |
| `Adaptive_Retail_Design_Rationale_and_Implementation_Notes_v1_1.txt` | Curated supporting digest | High-value rationale preserved in repo |
| `Adaptive_Retail_CSI_Rebaseline_CRM_Delta_Pack_v1_1.txt` | Curated supporting digest | Rebaseline implications and merge path preserved in repo |
| `Adaptive_Retail_System_Development_Snapshot_v1_0.md` | Exact / near-exact | Imported in PR #1 |
| `Adaptive_Retail_Change_Resolution_Matrix_v1_0.md` | Exact / near-exact | Imported in PR #3 |

## What PR #4 closed

PR #4 materially closes the largest practical gap by adding substantive in-repo working copies for the most important authoritative documents:
- roadmap
- architecture
- ICD core
- interface addendum
- technical requirements
- V&V plan
- coding AI governance charter

## Remaining delta types

1. Several authoritative documents are represented as curated extracts rather than line-for-line exports.
2. Earlier source-note files still exist alongside stronger repo-native extracts.
3. The repository now has usable, searchable grounding for implementation, but exact visual/layout fidelity still lives in the uploaded PDF/DOCX originals.

## Practical conclusion

After PR #4, the repository has:
- document-control structure
- authoritative/supporting/living separation
- delta reporting
- supporting rationale coverage
- substantive repo-native working copies of the active authoritative baseline

The remaining gap is mainly **fidelity**, not **practical absence**. For implementation and AI grounding, Git is now materially usable as a local source-of-truth workspace, while the uploaded originals remain the higher-fidelity source when exact wording or layout is required.
