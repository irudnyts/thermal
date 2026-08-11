# Implementation log

## Link FFmpeg decoding framework

- **Commit:** `Link FFmpeg decoding framework`
- **Intent:** Make the manually generated FFmpeg 8.1.2 libraries available to Stream before adding decoding code.
- **What changed:** Linked the static FFmpeg XCFramework to the app target and added a smoke test that calls FFmpeg's version API through a small Swift wrapper.
- **Important implementation details:** The XCFramework supplies separate arm64 slices for physical iPhones and Apple-silicon Simulators. Because it contains static libraries, it is linked but not embedded in the application bundle. Its generated module uses a narrow umbrella header so Swift does not scan unrelated platform-specific FFmpeg headers.
- **Verification performed:** The Debug build and all four tests passed on the iPhone 13 Pro Simulator running iOS 26.5, including an exact `8.1.2` version assertion. An unsigned Debug build also succeeded for the generic physical-iPhone destination.
- **Known limitations:** This checkpoint proves linkage only; it does not open UDP input or decode frames.
- **Relevant Swift concepts:** A module import exposes FFmpeg's C functions directly to Swift. `String(cString:)` converts FFmpeg's null-terminated version string into a Swift `String`.

## Fix FFmpeg 8.1.2 configure options

- **Commit:** `Fix FFmpeg 8.1.2 configure options`
- **Intent:** Correct the manual dependency build after FFmpeg rejected an obsolete configure option.
- **What changed:** Removed `--disable-postproc` from the FFmpeg build helper because FFmpeg 8.1.2 no longer provides the libpostproc component or its configure switch.
- **Important implementation details:** The remaining minimal-build switches are unchanged; libpostproc was already absent from FFmpeg 8.1.2, so removing its disable switch does not add functionality to the output.
- **Verification performed:** The helper passed `bash -n`. FFmpeg's configure phase succeeded for both arm64 iPhone and Simulator targets with exactly the intended libraries and components enabled. The Stream Debug build and all three tests also passed on the iPhone 13 Pro Simulator running iOS 26.5.
- **Known limitations:** The XCFramework still needs to be built by rerunning the manual dependency checkpoint.
- **Relevant Swift concepts:** None; this is a shell build-helper correction.

## Add reproducible iOS FFmpeg build helper

- **Commit:** `Add reproducible iOS FFmpeg build helper`
- **Intent:** Make the required FFmpeg 8.1.2 device and Simulator binary reproducible without committing third-party source or build output.
- **What changed:** Added a user-run build script, documented its prerequisites and generated files, and ignored downloaded sources and binaries.
- **Important implementation details:** The script builds static arm64 slices for iPhone and Apple-silicon Simulator, then packages them as one XCFramework. FFmpeg is configured for UDP/file input, MPEG-TS demuxing, H.264 parsing/decoding, and pixel conversion; programs, encoders, unrelated components, GPL, version-3, and nonfree code are disabled.
- **Verification performed:** `bash -n` accepted the helper, and the Debug build plus all three existing tests passed on the iPhone 13 Pro Simulator running iOS 26.5. The dependency build itself is intentionally reserved for the manual checkpoint.
- **Known limitations:** FFmpeg is not linked to Stream yet. Intel Simulator slices are out of scope because the project assumes an Apple-silicon Mac.
- **Relevant Swift concepts:** None; this checkpoint prepares a C library that a later Objective-C bridge will expose to Swift.

## Add portrait camera placeholders

- **Commit:** `Add portrait camera placeholders`
- **Intent:** Establish the portrait-only two-camera layout before introducing video decoding.
- **What changed:** Replaced the launch label with two equal, full-width 4:3 black panes, added the primary-stream listening status, locked the app to portrait, and added unit and UI coverage for the orientation and layout.
- **Important implementation details:** The two panes are stacked without spacing at the top of the screen. Stable accessibility identifiers make the status and pane geometry observable to UI tests.
- **Verification performed:** Built the Debug configuration and ran two unit tests plus one layout UI test on the iPhone 13 Pro Simulator running iOS 26.5; all three passed.
- **Known limitations:** Both panes are placeholders. The upper pane does not receive video yet, and the lower pane is intentionally reserved and black.
- **Relevant Swift concepts:** A small private SwiftUI `View` keeps the repeated camera-pane layout in one place. `aspectRatio` preserves the required 4:3 shape as the phone width changes.

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
