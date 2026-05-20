## ADDED Requirements

### Requirement: Cross-file sync discipline when propositions plugin is loaded

When the propositions plugin loads into a Claude Code session, the system SHALL apply the code-and-manuscript-sync discipline rule to any change that touches code, references, or manuscript content. The rule treats code (analysis/), references (references/), and manuscript (manuscript/docs/ and manuscript/*.tex) as three faces of a single deliverable; a change to one face MUST NOT be merged before the other affected faces are updated in the same PR or commit cluster.

#### Scenario: Code edit invalidates manuscript reference

- **WHEN** a code change deletes or renames a symbol that is referenced in any non-frozen manuscript file under manuscript/docs/ or manuscript/*.tex
- **THEN** the diagnosis output SHALL identify each affected manuscript file and the implementation SHALL update those files in the same PR or commit cluster

#### Scenario: Diagnosis must declare manuscript impact

- **WHEN** /idd-diagnose runs on a code or references change
- **THEN** the strategy section SHALL explicitly answer three questions: which manuscript/docs/ derivations are invalidated, which manuscript/*.tex theorems or proofs are invalidated, and whether the affected files are inside the cluster's implementation plan
- **AND** an explicit answer of "N/A — pure tooling change, manuscript unaffected" SHALL be permitted only when written out in the diagnosis text

#### Scenario: Verification rejects manuscript drift

- **WHEN** /idd-verify runs after a code or references change
- **THEN** the Regression Reviewer SHALL grep manuscript/docs/ and manuscript/*.tex for any deleted symbol
- **AND** any remaining reference inside a non-frozen living document SHALL produce a blocking finding that prevents PR pass

### Requirement: Submodule boundary does not split scope

The discipline SHALL treat the manuscript git submodule boundary as a deployment artifact, not a scope boundary. Changes affecting both the parent repository and the manuscript submodule SHALL be planned, opened, cross-linked, and merged together as one cluster.

#### Scenario: Cluster spans parent repository and manuscript submodule

- **WHEN** a code change in the parent repository invalidates content in the manuscript submodule
- **THEN** the implementation SHALL produce two cross-linked pull requests, one in the parent repository and one in the manuscript submodule repository
- **AND** the parent repository PR SHALL include a submodule pointer bump committed in the same cluster
- **AND** the parent PR SHALL NOT be merged before the manuscript PR is merged

### Requirement: Frozen subregions are exempt from sync

The discipline SHALL treat designated frozen historical records as exempt from the cross-file sync requirement. Frozen records include manuscript/docs/rounds/*.md, manuscript/docs/legacy/*, correspondence/*, and any path under archived/ or archive/. Lingering references inside frozen records SHALL NOT be flagged as dangling consumers; instead, the current living documents (for example manuscript/docs/STATE.md or review-summary.md) SHALL receive a scope-update note pointing to the new decision.

#### Scenario: Deleted symbol referenced only in frozen audit log

- **WHEN** a deleted symbol is grep-matched only inside files under manuscript/docs/rounds/ or any archived/ path
- **THEN** verification SHALL NOT flag the lingering reference as a blocking finding
- **AND** the same cluster SHALL add a scope-update note inside a non-frozen living document pointing to the new decision

#### Scenario: Deleted symbol referenced in living doc

- **WHEN** a deleted symbol is grep-matched in manuscript/docs/STATE.md or any non-frozen living manuscript document
- **THEN** verification SHALL flag a blocking finding
- **AND** the cluster SHALL update the living document in the same PR before merge
