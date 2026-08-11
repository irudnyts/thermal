# Implementation log

## Use iPhone 13 Pro as reference device

- **Commit:** `Use iPhone 13 Pro as reference device`
- **Intent:** Make iPhone 13 Pro the standard Simulator used to verify Stream without limiting normal iPhone compatibility.
- **What changed:** Updated the application README to name iPhone 13 Pro as the reference and run destination.
- **Important implementation details:** Xcode targets the iPhone device family rather than an individual model, so the project continues to support every iPhone running iOS 17 or newer.
- **Verification performed:** Built Stream and ran both unit and UI tests on the iPhone 13 Pro Simulator running iOS 26.5; both tests passed.
- **Known limitations:** The locally available iPhone 13 Pro profile runs iOS 26.5 because that is the installed Simulator runtime.
- **Relevant Swift concepts:** None; this change affects only the documented development destination.

## Initialize Stream iOS project

- **Commit:** `Initialize Stream iOS project`
- **Intent:** Establish a minimal, buildable SwiftUI iPhone application under `/app`.
- **What changed:** Added the Stream application, Xcode project, unit-test target, UI-test target, assets, and introductory README.
- **Important implementation details:** The product name is `Stream`, the bundle identifier is `com.irudnyts.stream`, the minimum deployment target is iOS 17, and only iPhone destinations are enabled.
- **Verification performed:** Built the Debug configuration for a generic iOS Simulator destination with Xcode 26.6. Ran the unit and UI tests on an iPhone 17 Pro Simulator running iOS 26.5; both tests passed.
- **Known limitations:** This commit is only the application shell. It does not yet lock portrait orientation, show camera panes, receive UDP packets, or decode video.
- **Relevant Swift concepts:** `@main` identifies the application entry point. A SwiftUI `WindowGroup` supplies the app's main window and displays `ContentView`.
