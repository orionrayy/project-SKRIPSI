# ORCHESTRATION_MEMORY — Public Canonical Project Memory

**Memory version:** 1.4.2  
**Project:** `orionrayy/project-SKRIPSI`  
**Updated:** 2026-11-19 (Asia/Jakarta)  
**Platform baseline:** 0.8.0  
**Repository visibility:** public (pre-existing setting; no setting change made).

## 1. Source precedence and provenance

This file is the public, sanitized orchestration memory. The canonical phase state is `config/pipeline/PHASE_LEDGER.json`. Private working directories, per-record research data, source URLs/locators, abstracts, participant information, thesis files, Turnitin reports and private QA reports are deliberately excluded. Historical chat share URLs and private archive hashes are not reproduced here.

The public state derives from the validated governance bootstrap (ledger 2.3.0), public aggregate phase reports and the platform v0.8.0 source snapshot. The platform archive and this repository's Git commit are separate provenance records.

## 2. Research-governance state

- **P0 — COMPLETE_AND_APPROVED:** scoped governance baseline under APR-P0-001. This is not a blanket institutional, ethics, legal or privacy certification.
- **P1 — COMPLETE_AND_APPROVED:** accepted 50-record bibliographic eligibility corpus, within APR-P1-001 scope. It is not a full-text-reviewed or systematically coded thesis corpus. Access profile: 25 partial-text-reviewed, 18 abstract-only, 7 metadata-only and 0 full-text-reviewed.
- **P2 — VALIDATION_PASSED_APPROVAL_PENDING:** AUTH-P2-001 authorizes P2 only. Aggregate result: 50 linked record shells, 214 abstract-level observations, 40 records with abstract observations, 3 without content observations due to access/retrieval limitations, 7 metadata-only and 0 unresolved abstract locators. Human acceptance APR-P2-001 remains blank. Independent second coder is NOT_RUN; semantic review is SELF_REVIEW_ONLY.
- **P3–P9 — NOT_STARTED / NOT_AUTHORIZED:** each phase requires predecessor completion/acceptance and its own explicit authorization.

Platform test results do not change research phase status. No AI-generated approval is permitted.

## 3. Platform architecture and releases

Platform development progressed through local engineering checkpoints v0.5.0–v0.8.0. The current public source baseline is v0.8.0 and includes:

- Evidence/source provenance, claim-evidence links and methodology alignment.
- A bounded descriptive statistical engine with transaction recovery, reproducibility and diagnostics.
- Evidence-linked DOCX/PDF document engineering and document audits.
- Revision-pair and marked-region QA.
- Empirical consistency gates for instrument constructs, paired tests, ICC and causal interpretation.
- Local-only Turnitin report metadata and report-comparison QA; no thesis body text storage or detector evasion.

Recorded local engineering validation: 200/200 unit/regression tests, 29/29 JSON Schemas (Draft 2020-12), compileall, phase-ledger validator and CLI smoke tests passed. GitHub Actions CI must be verified from an actual workflow run before making a remote CI claim.

## 4. Public/private separation

Public repository allowlist: platform code, schemas, synthetic test fixtures, generic documentation, sanitized governance records and aggregate phase status.

Private-only material: P1/P2 datasets, evidence/source registers, abstract text, exact source routes/locators, per-record codes, adjudication and coverage tables, private packages, thesis DOCX/PDF, Turnitin reports, marked-region exports, participant names/scores, case-specific hashes, credentials and local caches.

The repo must remain free of raw participant-level or private source material. Public availability does not grant rights to third-party source content; no software license is declared unless a separate approved license is added.

## 5. Repository activation and publication checkpoint

The first repository content commit created the public README on `main`: `c51b223fcd4803006afbba9d68e891216b83ce0a`. On 2026-11-11, the sanitized source publication completed through the one-shot GitHub Actions expansion workflow:

- Bootstrap commit: `ce24e8a4051658de4412aded3ca43602d8fbc750`.
- Expansion workflow run #2: **SUCCESS**, run ID `43002256443`, completed at 2026-11-11 17:17:49 WIB.
- GitHub Actions expansion commit on `main`: `a667940306d57d83032ad973985c504fb7774a30`.
- Expanded tree: `a8f3c08429582d2ff62e912a5f73fb191cd65503`; recursive tree read was not truncated.
- Remote tree inventory: **133 file blobs and 49 directories**. It contains **130 manifest-allowlisted source files**, `MANIFEST.sha256`, the distribution TAR.XZ archive, and its SHA-256 sidecar.
- Archive: 169,800 bytes; SHA-256 `bcade06f387de89a1c93dd468ff8ff4baf474c4f8976284e2091a1bce6ef805f`. Its Git blob SHA `311cd93a46715a3c61a1e9cbb6c2e6a3164af644` matches the locally verified archive bytes.
- Repository metadata at verification: public, active, default branch `main`, one branch, reported size 612 KB.

The expansion job's reconstruction/checksum, safe extraction, dependency/renderer installation, complete source validation, and transport-fragment removal/commit steps all completed successfully. The source-validation step runs the manifest verifier, phase-ledger validator, Python compileall, 200-test unit/regression suite, editable package installation without dependency changes, and CLI help smoke test.

The independent cross-platform `Project Skripsi CI` matrix has **not yet been verified on the expanded tree**: the bootstrap-triggered CI run was intentionally skipped, while an earlier run against the pre-expansion repository failed because the source tree was not yet present. Do not describe the six-platform matrix as passed until a post-expansion run is observed. No release, deployment, force-push, or visibility change was performed. The authenticated GitHub account matches the repository owner; the local Git author remains unconfigured, so no local commit is claimed.

## 6. Public repository contents and private-data boundary

The expanded public tree contains the reusable platform source, Python package and CLI, 29 JSON Schemas, synthetic regression suite, generic documentation, project/workspace templates, canonical sanitized P0–P9 governance snapshot, aggregate-only P0/P1/P2 status, `MANIFEST.sha256`, and the deterministic TAR.XZ distribution archive with its checksum sidecar. The manifest contains 130 source-file entries; the archive contains those 130 files plus `MANIFEST.sha256`.

Private material remains excluded: P1/P2 record-level datasets, source/evidence registers, abstract text and exact locators, extraction/coding/adjudication matrices, private QA exports, individual thesis DOCX/PDF, actual Turnitin reports, report/submission identifiers, participant-level data, credentials, databases and caches. The Turnitin-named source module, schema, generic documentation, and tests are platform functionality using synthetic test fixtures; they are not actual Turnitin report exports or case-level QA files.

The repository remains a platform publication, not a publication of the user's thesis or research corpus. Public source availability does not grant redistribution rights to third-party material, and no software license is declared until a separate license is approved and added.

## 7. Recovery, verification, and continuation protocol

On every invocation:
1. Read this memory and `config/pipeline/PHASE_LEDGER.json`; verify the current `main` head and repository tree rather than relying on a previous checkpoint.
2. Verify the current public-source manifest entry count, archive SHA-256, safe-path rules, and absence of private thesis/report/database/participant artifacts before any further publication.
3. Distinguish engineering checks from research-phase validation, human acceptance, and phase-specific authorization.
4. Continue the earliest incomplete authorized work item. Preserve P0 and P1 accepted scopes; P2 remains `VALIDATION_PASSED_APPROVAL_PENDING` with APR-P2-001 blank; P3–P9 remain `NOT_STARTED / NOT_AUTHORIZED`.
5. The project owner's standing instruction to continue implementation without repeated operational approvals does not allow the system to invent a P2 acceptance decision, waive research ethics or source restrictions, or self-authorize P3–P9. Keep execution authorization, human acceptance, and evidence validation separate.
6. Update the canonical ledger and this memory only from verified repository and artifact evidence. Do not claim a workflow, package installation, external review, or academic acceptance unless its actual result is observed.


## 8. Visual presentation engineering checkpoint — 2026-11-17

- Added an optional PowerPoint toolkit on feature branch feat/powerpoint-morph-toolkit: a standard-library OOXML Morph patcher/inspector, optional python-pptx freeform and preset picture-geometry helpers, a CLI, documentation, and synthetic regression tests.
- Morph transitions are attached to destination slides. The inspector resolves displayed order from presentation slide IDs and relationships, checks ZIP CRC, Morph option/duration, Fade fallback, duplicate forced names and source/destination name pairs.
- Local validation on the current Linux runtime: 12/12 toolkit tests PASS, Python compileall PASS, and a 13-slide demonstration deck passes structural inspection with Morph targets on slides 5, 7 and 9, 950 ms, 30 forced object names, and no reported structural errors. LibreOffice rendered all 13 slides for visual review.
- Microsoft PowerPoint slide-show playback is NOT_VERIFIED. LibreOffice PDF rendering does not exercise the Microsoft Morph engine; desktop PowerPoint preview remains a required acceptance check.
- The demonstration PPTX, generated demo photos, uploaded reference videos, and frame captures are local deliverables only; none are added to the public source tree. The public toolkit documentation records which visual mask components remain picture alpha assets rather than live Boolean geometry.
- The research phase ledger was not changed. P2 remains VALIDATION_PASSED_APPROVAL_PENDING with APR-P2-001 blank; P3–P9 remain NOT_STARTED / NOT_AUTHORIZED. Engineering tests do not change research governance.


## 9. Morph control investigation — 2026-11-18

- The user reports that the upper small ball moves through Morph in PowerPoint while the lower large ball does not. The uploaded six-slide package contains two relevant groups: upper `Group 9` and lower `Group 7`. Both groups retain stable names and IDs across the sequence. The received slide XML, however, contains Fade transitions on destination slides and no `p159:morph` element; the source package therefore does not preserve the playback state the user observed.
- Static geometry inspection shows that the upper group translates while retaining its outer extent. The lower group changes outer width/height across keyframes; its nested freeform has 13 edit points on slides 1–5 and 10 on slide 6. This is a diagnostic distinction, not proof of the Morph engine's matching decision.
- Created three local variants from the exact uploaded package: `MORPH_MATCHING_AUTO_BASELINE.pptx` (original names), `MORPH_MATCHING_FORCE_LARGE_GROUP.pptx` (lower group named `!!large-ball` on all six slides), and `MORPH_MATCHING_FORCE_CHILD_FREEFORM.pptx` (nested `Freeform 8` named `!!large-ball-path`, while `Group 7` remains unchanged). All use `p159:morph option="byObject"` on destination slides 2–6, 1,250 ms, and the explicit Fade fallback. All pass ZIP CRC/XML checks; LibreOffice renders static slide endpoints only. These checks do not verify native PowerPoint playback.
- Microsoft documents the `!!` prefix as a matching override: the same unique forced name is applied to corresponding shapes on adjacent slides. Keep matching object types consistent and do not reuse a forced name for multiple objects on one slide.
- Corrected the toolkit guide and changelog to match the implemented serializer: `Requires="p159"`, with `p159` scoped on `mc:Choice` and `p14` scoped on the Morph `p:transition`. The inspector now records OOXML container types for forced names and rejects cross-type pairs such as `p:sp` → `p:grpSp`; regression tests cover stable group/child pairs and mismatched types.
- GitHub Actions run #143 completed successfully: 6/6 Ubuntu/Windows matrix jobs across Python 3.10–3.12, each passing 220 tests. PR #3 remains open and Draft; the update did not merge or modify `main`.
- Microsoft PowerPoint playback of the two uploaded-source variants remains NOT_VERIFIED. P0–P9 research governance and acceptance states remain unchanged.

## 10. Free native-Morph reference corpus — 2026-11-19

- Collected and audited 54 unique public PPTX references from three repositories: HY-hue113/ppt-effects (24), iOfficeAI/OfficeCLI (28), and SorenWang/morph_motion_pptx_skill (2). The corpus has 54/54 unique SHA-256 hashes and all source packages passed ZIP CRC and active-slide OOXML checks.
- The 22-file priority A+B shortlist was downloaded by GitHub Actions and independently verified on 2026-11-19: **22/22 PASS**, 0 failures. The job validates file size, SHA-256, ZIP CRC, active slide order, Morph option, active Morph transitions, strict object name/type matches, and changed object geometry. It deletes downloaded PPTX binaries from the runner and uploads only the JSON verification report.
- Priority A+B aggregate: 240 active slides, 218 active slides containing native Morph, 209 Morph destination transitions, 3,149 unique name/type object matches across transitions, and 845 matched objects whose position, size, or rotation changed. Strong examples include the 19-slide segmented-photo sequence, 12-slide typography sequence, 25-slide circular shutter, 12-sector fan reveal, curved gold aperture, blur mask, and photo carousel.
- Full-corpus aggregate audit: 517 active slides, 454 Morph transitions, 6,693 unique name/type matches, and 2,976 matched-object geometry changes. Thirty transitions have no strict name/type match; treat these as inspection warnings, not automatic proof of missing interpolation.
- The reproducible local downloader and offline regression tests are in the release ZIP `MORPH_PPTX_DATASET_INDEX_AND_DOWNLOADER.zip`. It uses Python standard library only. `--priority B` downloads all 22 A+B sources; default downloads the full 54-file corpus. Local session DNS access did not allow direct binary download; GitHub Actions provided the successful network fetch/verification evidence.
- Brush-stroke mask references are kept outside the native-Morph count. Showeet's free 41-layout brush mockup collection is a static/editable picture-mask resource requiring attribution; it does not claim to provide native Morph animation. Do not count it as Morph. Embedded photos and source decks with unclear asset-level redistribution rights are not vendored into the repository.
- Structural checks and GitHub CI do **not** verify Microsoft PowerPoint playback. Native Desktop PowerPoint preview and visual acceptance remain NOT_VERIFIED and required before claiming the toolkit reproduces the reference videos.
- No research phase ledger, P0–P9 approval state, or `main` branch state was changed. Dataset work remains isolated to this Draft Morph PR.


## 11. Native custom picture-mask geometry — 2026-11-19

- Extended the optional PowerPoint geometry toolkit with set_picture_freeform_geometry() and set_picture_custom_path(). Custom DrawingML geometry is written into the picture shape itself, retaining native p:pic identity, image relationship and picture crop. Both polygon and quadratic/cubic Bezier path commands are supported in normalized picture coordinates.
- Added defensive validation for malformed commands, point arity, non-finite/out-of-bounds points, move-command position/count, minimum distinct anchors, and coordinate scale. The image is not rasterized or embedded as a brush texture; this is editable picture clipping geometry.
- Local validation: 14/14 PowerPoint geometry tests PASS, including save/reload, crop preservation, Bezier path structure, geometry replacement and invalid-path rejection. LibreOffice static render smoke test displays the custom Bezier picture mask; this does not verify PowerPoint Morph playback.
- Toolkit documentation records the custom-mask API and Morph keyframe constraints. Microsoft PowerPoint Desktop playback remains NOT_VERIFIED.
- No phase ledger, research approval or acceptance state changed. PR #3 remains Draft and unmerged; main is unchanged.


## 12. Reproducible custom-mask Morph example — 2026-11-19 (initial iteration superseded)

- The first five-slide prototype used a native `p:pic` with `a:custGeom`. The user reported that no picture-mask change appeared in playback. XML parsing, ZIP CRC and LibreOffice static rendering were insufficient evidence; the initial demo is treated as a failed acceptance attempt.
- The picture-object custom-path helper remains available for static editable picture clipping, but it is not described as a verified Morph-mask implementation.
- This initial implementation was superseded by a freeform shape with image fill. The corrective investigation and current acceptance boundary are recorded in the following section.


## 2026-11-19 — Morph demo feedback and revised picture-mask strategy

- User reported that the custom-picture-mask Morph demo showed no visible change in their playback environment. Treat this as a failed acceptance test, not as a user setup error.
- The first demo used p:pic with p:spPr/a:custGeom. ZIP CRC, OOXML structure and LibreOffice static endpoints passed, but those checks did not prove Morph interpolation. Do not label that approach playback-verified.
- Revised experimental implementation: use a native p:sp freeform custom shape with p:spPr/a:blipFill picture fill. Match the same unique !!hero-photo-mask shape across adjacent slides; retain identical command topology/winding and change corresponding Bezier control points gradually.
- Regression test must prove that all five custom path serializations are different, in addition to checking one move, ten cubic Bezier segments, close path, image fill and Morph on destination slides 2–5.
- New artifact MORPH_CUSTOM_SHAPE_PICTURE_FILL_DEMO.pptx has five visibly different static keyframes and native Morph declarations. LibreOffice static rendering passes. Microsoft PowerPoint Desktop/mobile playback is still NOT_VERIFIED until the user tests it in Slide Show.
- Canva Match & Move is not PowerPoint Morph. Canva's page-transition UI supports Match & Move, but the connected Canva edit API available here has no page-transition operation. Never set Dissolve as a substitute or claim Match & Move was programmatically applied.
- PR #3 remains Draft. Do not merge without explicit user authorization. No P0–P9 governance/acceptance state is changed.


## 11. Morph playback feedback hardening — 2026-11-19

- The first custom-picture-mask deliverable used p:pic with a:custGeom. The user reported no visible change during playback; this was treated as a failed demo rather than accepted from XML/static-render checks.
- The feature branch generator was revised to use a native p:sp freeform filled by a:blipFill. The matched shape retains one unique !!hero-photo-mask name across five adjacent keyframes. The five Bezier paths differ, and the demo keyframes also vary shape position and scale.
- The rebuilt v4 artifact uses the p:sp + a:blipFill method and a transition order of p:cSld, p:clrMapOvr, then mc:AlternateContent. ZIP CRC, XML structure, five distinct geometry endpoints, and LibreOffice static rendering pass.
- Microsoft PowerPoint Desktop playback remains NOT_VERIFIED. This runtime cannot simulate the proprietary Morph engine; no final playback-success claim is made.
- Canva Match & Move is a Canva-native page transition, not the PowerPoint Morph OOXML element. The connected Canva editing operations currently exposed here have no page-transition setter. Do not substitute Dissolve or claim Match & Move was configured through the integration.
- P0–P9 research governance and acceptance states are unchanged. PR #3 remains Draft and is not merged.

## 12. Canva Match & Move compatibility boundary — 2026-11-19

- The user confirmed the latest PPTX custom-mask demo was imported/opened in Canva and did not display Morph. This is a failed acceptance result for the Canva target.
- Native PowerPoint `p159:morph` and Canva Match & Move are different systems. The PPTX import workflow converts presentation content into Canva design pages; do not assume it carries PowerPoint Morph metadata into Canva page transitions.
- Canva's documented Match & Move process uses page keyframes and requires selecting Match & Move from the transition control between pages. The Canva connector operations available to this project do not expose a page-transition setter; automated transition application and playback verification are unavailable.
- Do not substitute Dissolve. Do not claim Canva Match & Move is configured unless it is visibly selected and previewed in Canva.
- The local PPTX v4 is a PowerPoint-only Morph candidate and is not a Canva animation deliverable. Microsoft PowerPoint Desktop playback remains NOT_VERIFIED. Canva animation is FAILED for the PPTX-import path.
- Initial Canva design search returned no match. A later continuation created an editable five-page Canva keyframe test (design `DAHbXq0gvl0`, edit URL `https://www.canva.com/d/B57HXK3Xjxry66_`). Read-back confirms one repeated image `mediaId` across all pages, but page-scoped element locator IDs differ. This verifies imported editable keyframes and shared media only, not Match & Move identity or playback. No transition was set; the connected Canva API has no transition setter.
- PR #3 remains Draft and unmerged. No research phase ledger, P0–P9 approval state, or `main` content was changed.


## 13. Canva keyframe compatibility test — 2026-11-19

- Created an editable five-page Canva presentation from a local PPTX keyframe fixture: design ID `DAHbXq0gvl0`, edit URL `https://www.canva.com/d/B57HXK3Xjxry66_`, view URL `https://www.canva.com/d/hXM7cyKsey6Ds-y`.
- Canva read-back confirms five editable fixed pages at 1920×1080. The hero is an editable image-filled shape. All five pages reference the same image `mediaId` (`MAHbXkHhMmw`); per-page element locator IDs differ.
- The keyframes vary position, dimensions and rotation. Source fixture `CANVA_MATCH_MOVE_KEYFRAME_TEST.pptx`, SHA-256 `d6e55dd5aa21af85466dc4662a973c3ea94c1b4e5e94221370a108e76b84905b`; ZIP CRC PASS, five active slides, one repeated source image, five distinct transforms.
- This is an import/keyframe compatibility fixture, not a Match & Move playback PASS. A shared media ID proves asset reuse, not transition-matcher object continuity.
- No transition was applied. Canva's connected API has no transition setter; no Dissolve substitute was used. Manual Match & Move selection and preview for all four page boundaries remain pending. For stronger identity continuity, duplicate the first page inside Canva and change the duplicated element.
- Canva animation acceptance remains PENDING. The earlier PPTX Morph import attempt remains FAILED for Canva. Microsoft PowerPoint Desktop playback of the separate native Morph demo remains NOT_VERIFIED.
- PR #3 remains Draft and unmerged; no `main`, P0–P9 governance, or approval state changed.
