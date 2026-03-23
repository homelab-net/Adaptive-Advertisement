# Adaptive Advertisement Source Baseline

This folder imports the current project documentation baseline into the repository as text-first source documents.

## Curation rule

The import follows the active document-precedence rule:
- highest revision first
- archived or superseded material is context only
- guiding and living artifacts are separated from authoritative baselines

## Structure

- `docs/authoritative/` — current baseline documents used first for implementation and verification
- `docs/authoritative/icd/` — current interface-control baselines
- `docs/supporting/` — directional or implementation-support documents that do not override authoritative baselines
- `docs/living/` — operational artifacts intended to be updated during implementation

## Current authoritative set imported

1. Software Selection Directive
2. Golden Roadmap V2
3. System Architecture Document
4. Consolidated ICD v1.0
5. Interface Addendum v1.0
6. Technical Requirements Package
7. Verification and Validation Plan
8. Pilot Validation Protocol v1.0
9. Coding AI Governance Charter v1.0

## Supporting or living artifacts imported

- Target End-State Vision v1.0
- Storage Retention and Eviction Guidance v1.0
- Design Rationale and Implementation Notes v1.1
- CSI Camera Rebaseline CRM Delta Pack v1.1
- System Development Snapshot v1.0
- Change Resolution Matrix v1.0

## Not promoted as active baseline in this import

Older roadmap-form material already absorbed by Golden Roadmap V2 is intentionally not duplicated as a separate active baseline.
The CSI rebaseline delta pack is imported as supporting change-control context, not as the active authority.
