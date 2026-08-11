# iOS application instructions

This directory contains the iOS application.

## Swift

- Prefer simple, idiomatic Swift.
- Optimize for readability by a developer learning Swift.
- Avoid clever abstractions and premature generalization.
- Explain unfamiliar Swift concepts in the post-commit report.
- Prefer Apple frameworks over third-party dependencies.
- Follow existing SwiftUI patterns in the project.

## Verification

After changing Swift code:

- Build the Xcode project.
- Run relevant tests.
- Resolve compiler warnings introduced by the change.
- Do not commit code that does not compile unless explicitly instructed.