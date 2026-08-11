# AGENTS.md

## Primary goal

Optimize for:
1. Understandability
2. Traceability
3. Small, reversible changes
4. Correctness
5. Simplicity

Do not optimize for implementing the largest possible amount of work in one pass.

## Work in small commits

Before implementing any non-trivial feature:

1. Inspect the relevant existing code.
2. Create a short implementation plan.
3. Split the work into small, logically independent commits.
4. Describe each proposed commit before making changes.

Each commit should represent exactly one understandable change.

Prefer:
- No more than 5 implementation files changed per commit.
- No more than approximately 200 changed lines per commit.

These are guidelines, not reasons to artificially split coherent code.

If a commit needs to exceed either guideline, explain why before implementing it.

Generated files and project metadata may be excluded from these limits when appropriate.

## Human checkpoint

Unless explicitly instructed otherwise:

- Implement only ONE planned commit at a time.
- Build and test the change.
- Commit it.
- Report what changed.
- STOP before starting the next planned commit.

Do not implement the entire multi-commit plan in one pass.

## Before each commit

State:

- Intent of the commit.
- Files you expect to modify.
- Why each file needs to change.
- Expected behavior after the commit.

If you discover that the proposed scope is substantially wrong, stop and revise the plan rather than silently expanding the change.

## After each commit

Report:

- Commit hash and commit message.
- Files changed.
- What was implemented.
- Build/tests performed and their results.
- Any known limitations or risks.
- What the next planned commit would do.

## Code changes

Do not:

- Refactor unrelated code.
- Rename unrelated types or files.
- Reformat unrelated files.
- Introduce abstractions that are not needed for the current task.
- Add third-party dependencies without explicit approval.
- Replace working code merely because another approach appears cleaner.

Prefer the smallest change that correctly implements the requested behavior.

## Swift guidelines

Prefer straightforward, idiomatic Swift that a beginner can follow.

Avoid:
- Clever language tricks.
- Premature generic abstractions.
- Deep inheritance.
- Unnecessary protocols.
- Unnecessary indirection.
- Large types doing many unrelated things.

When introducing a Swift concept that may not be obvious to a beginner, briefly explain it in the post-commit report.

Prefer Apple-provided frameworks over third-party dependencies unless there is a strong reason otherwise.


## Verification

Before committing:

1. Build the project.
2. Run relevant existing tests.
3. Add or update tests when the behavior being changed can reasonably be tested.
4. Review the diff for accidental unrelated changes.

Never claim that a build or test passed unless it was actually run.

If verification cannot be performed, clearly state why.

## Documentation

Maintain `CHANGES.md` as a developer-oriented implementation log.

For every completed commit, add:

- Commit
- Intent
- What changed
- Important implementation details
- Verification performed
- Known limitations
- Relevant Swift concepts, when useful

Keep entries concise but detailed enough that someone unfamiliar with Swift can understand the purpose of the change.

`CHANGES.md` does not count toward the normal per-commit file or line limits.

## Simplicity rule

When multiple implementations are reasonable, prefer the implementation that:

1. Uses less code.
2. Introduces fewer new concepts.
3. Uses existing project patterns.
4. Is easier to delete or modify later.
5. Is easier for a beginner to understand.

Do not build infrastructure for hypothetical future requirements.

## Dependencies

Do not install, add, upgrade, downgrade, or remove dependencies. Instead, explain explicitly how to install them manually. 

This includes, but is not limited to:

* Swift Package Manager packages
* CocoaPods
* Homebrew packages
* npm packages
* Python packages
* system packages
* command-line tools
* Xcode extensions or plugins

If a dependency is required:

1. Explain why the dependency is needed.
2. Explain what it will be used for.
3. Explain whether the same result can reasonably be achieved without adding the dependency.
4. Provide the exact steps or commands I should use to install it myself.
5. Explain what files the installation is expected to modify.
6. STOP and wait for me to install it.

Do not run installation commands yourself.

Do not modify dependency manifests or lockfiles unless I explicitly approve the dependency first.

Examples of files that should not be changed without approval include:

* `Package.swift`
* `Package.resolved`
* `Podfile`
* `Podfile.lock`
* `package.json`
* `package-lock.json`
* `requirements.txt`
* dependency-related Xcode project settings

After I confirm that the dependency has been installed, verify that it is available and then continue the implementation.

Prefer built-in Apple frameworks and existing project dependencies whenever they can reasonably solve the problem.
