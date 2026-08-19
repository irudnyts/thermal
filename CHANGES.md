# Implementation log

## Save synchronized pairs on UDP capture commands

- **Commit:** `Save synchronized pairs on UDP capture commands`
- **Intent:** Record an overlay-free visible and thermal image pair when the Raspberry Pi receives the iPhone's capture command.
- **What changed:** Added a non-blocking UDP listener on port 5001, exact `CAPTURE` command counting, per-launch batch allocation, numbered pair saving, failure cleanup, and Git exclusion for runtime capture data.
- **Important implementation details:** Each command consumes the next synchronized pair before resizing, concatenation, or telemetry rendering. Both frames are encoded to temporary PNGs before their final names are published; failed pairs are removed and do not advance the image number.
- **Verification performed:** Python syntax compilation succeeded. All 14 focused unit tests passed, including batch allocation, exact command filtering, raw-frame selection, multiple pending requests, failed-pair cleanup, streaming continuity, and socket shutdown.
- **Known limitations:** UDP provides no delivery acknowledgement or authentication. Physical camera capture and filesystem behavior still require Raspberry Pi verification.
- **Relevant Python concepts:** A non-blocking socket lets the existing synchronization loop poll for commands without adding another thread. Temporary files prevent a failed PNG encode from leaving a normal-looking incomplete pair.

## Display the composite stream in landscape

- **Commit:** `Display the composite stream in landscape`
- **Intent:** Present the complete two-camera video and burned-in telemetry as one unobstructed landscape stream on iPhone.
- **What changed:** Replaced the portrait two-pane layout with one full-available-area aspect-fit stream, locked the app to landscape right, hid the app status during playback, updated orientation and layout tests, and documented operation with the two-camera sender.
- **Important implementation details:** The decoder continues to use each frame's native dimensions, so no transport or decoding changes are required for 1280×560 input. SwiftUI preserves the complete image and uses the existing black background as letterboxing; lifecycle-driven receiver start and stop behavior is unchanged.
- **Verification performed:** The arm64 Simulator Debug build passed. All eight unit tests and the landscape layout UI test passed on the iPhone 13 Pro Simulator running iOS 26.5. An unsigned generic-iPhone Debug build passed, and its generated Info.plist contains only `UIInterfaceOrientationLandscapeRight` for iPhone.
- **Known limitations:** Physical Raspberry Pi-to-iPhone playback still requires hardware verification. Only `UIInterfaceOrientationLandscapeRight` is supported.
- **Relevant Swift concepts:** A conditional expression passes no status view while the model is playing. SwiftUI's aspect-fit image rendering scales a frame without cropping or changing its proportions.

## Stream the synchronized two-camera composite

- **Commit:** `Stream the synchronized two-camera composite`
- **Intent:** Send the side-by-side camera image and its burned-in telemetry footer to the iPhone over the existing UDP video protocol.
- **What changed:** Connected the OpenCV-frame encoder to the synchronized capture loop, loaded the destination from `MAC_IP` and `PORT`, sent each accepted 1280×560 composite before displaying it locally, and closed the sender during shutdown.
- **Important implementation details:** Encoding happens after the telemetry footer is drawn, so the statistics are video pixels rather than a separate app overlay. The sender is created before camera threads start, and the existing cleanup path now stops the threads, flushes the encoder, and closes the preview for normal exit, interruption, and streaming failures.
- **Verification performed:** Python syntax compilation and the focused unit-test suite passed, including an integration-style test that runs the main loop with fake cameras and confirms the complete 1280×560 frame is sent and the sender is closed.
- **Known limitations:** Physical camera capture, Raspberry Pi encoding performance, network delivery, and iPhone playback still require hardware verification. The destination remains configured through `.env`.
- **Relevant Python concepts:** A `finally` block performs cleanup even when encoding or transmission raises an exception. Environment variables keep the receiver address outside the source code.

## Add an OpenCV-frame UDP encoder

- **Commit:** `Add an OpenCV-frame UDP encoder`
- **Intent:** Provide a small sender that can encode an already-composed OpenCV frame for the iPhone's existing UDP video protocol.
- **What changed:** Added a PyAV-backed sender that converts fixed-size BGR frames to H.264/YUV420P, muxes them as MPEG-TS, and writes UDP packets using the existing 1316-byte packet size convention.
- **Important implementation details:** The encoder uses a 2 Mbps bitrate, a 30-frame keyframe interval, repeated headers, no B-frames, and x264's low-latency settings. Frames receive sequential presentation timestamps, and shutdown flushes delayed packets exactly once. Encoder setup failures are reported as a clear runtime error.
- **Verification performed:** Python syntax compilation succeeded for all four Python scripts. All eight unit tests passed, including encoder configuration, BGR conversion, packet muxing, dimension validation, flushing, idempotent shutdown, and unavailable-encoder reporting. Hardware streaming remains to be checked on the Raspberry Pi.
- **Known limitations:** The helper is not connected to the synchronized camera loop yet. Hardware encoding availability and performance must be verified on the Raspberry Pi.
- **Relevant Python concepts:** `Fraction` represents the exact frame time base without floating-point rounding. The sender owns the PyAV container and stream and makes cleanup idempotent so repeated shutdown requests are safe.

## Add two-camera FPS and synchronization telemetry

- **Commit:** `Add two-camera FPS and synchronization telemetry`
- **Intent:** Show the actual capture speed of each camera and the rate and timing quality of synchronized frame pairs.
- **What changed:** Added independent one-second rolling FPS measurements to both capture threads, an accepted-pair FPS measurement to the synchronization loop, and a black OpenCV footer below the side-by-side preview. The footer shows each camera's FPS, synchronized FPS, and the signed Pi-minus-thermal timestamp difference in milliseconds.
- **Important implementation details:** FPS values travel with their captured frames, avoiding shared mutable counters between threads. OpenCV adds and draws the footer with `copyMakeBorder`, `getTextSize`, and anti-aliased `putText`; text is centered beneath the relevant stream. The script now starts through a `main()` function so its calculation and rendering helpers can be imported without starting camera threads.
- **Verification performed:** Python syntax compilation succeeded. Three deterministic unit tests passed for FPS warmup, rolling-window expiration, footer dimensions, black footer pixels, formatted values, and text placement. OpenCV and Picamera2 are unavailable in the local environment, so the tests use narrow fakes and hardware rendering remains to be checked on the Raspberry Pi.
- **Known limitations:** Metrics appear only in the local preview. The first sample displays `--`, the synchronization error describes only the current accepted pair, and hardware camera behavior has not been verified locally.
- **Relevant Python concepts:** A `deque` efficiently removes timestamps that leave the rolling window. A `main()` guard prevents hardware startup when another module imports this script for testing.

## Add minimal synchronized two-camera display

- **Commit:** `Add minimal synchronized two-camera display`
- **Intent:** Show Raspberry Pi and thermal camera images together with close capture times.
- **What changed:** Added a standalone script that captures both cameras on separate threads, timestamps frames with a monotonic clock, drops old queued frames, pairs frames within 50 milliseconds, and displays them side by side at 1280×480.
- **Important implementation details:** Each camera uses a two-frame bounded queue to limit latency. The main loop discards the older candidate until the timestamps are close enough. Pressing `q`, `Ctrl+C`, or encountering a camera error stops both capture loops and releases their resources.
- **Verification performed:** Python syntax compilation succeeded. Hardware capture and display require verification on the Raspberry Pi with both cameras attached.
- **Known limitations:** Camera indices, resolution, frame rate, and synchronization tolerance are fixed constants. The script displays locally and does not send UDP video.
- **Relevant Python concepts:** Threads let the two blocking camera APIs capture independently, while thread-safe queues transfer timestamped frames to the display loop.

## Configure the Apple development team

- **Commit:** `Configure the Apple development team`
- **Intent:** Let Xcode automatically sign Stream for development with the selected Apple developer account.
- **What changed:** Set development team `YNDPP33A7W` for the app target's Debug and Release configurations. Xcode also refreshed the displayed project-reference labels for the vendored FFmpeg XCFramework and the MPEG-TS test fixture without changing their paths or build-phase membership.
- **Important implementation details:** Automatic signing remains enabled, the bundle identifier remains `com.irudnyts.stream`, FFmpeg remains linked from `Vendor/FFmpeg/FFmpeg.xcframework`, and `Fixtures/test_640x480.ts` remains copied into the test bundle as a resource.
- **Verification performed:** The Debug build and all eight unit tests plus the camera-layout UI test passed on the iPhone 13 Pro Simulator running iOS 26.5. Xcode emitted a debugger-version-store warning that did not affect the successful test run.
- **Known limitations:** Xcode now classifies the MPEG-TS fixture's `.ts` extension as TypeScript in project metadata. It remains a resource, so this affects Xcode's file presentation rather than the test bundle's behavior.
- **Relevant Swift concepts:** None; this change affects Xcode project metadata and code signing.

## Display and manage the primary UDP stream

- **Commit:** `Display and manage the primary UDP stream`
- **Intent:** Connect the decoder to the portrait UI and make stream ownership follow the application lifecycle.
- **What changed:** Added the observable camera model, rendered decoded frames aspect-fit in the upper pane, exposed listening/playing/reconnecting/error text, kept the lower pane black, added the local-network purpose string, and documented physical-iPhone operation.
- **Important implementation details:** The model fixes the v1 endpoint at `udp://0.0.0.0:5000`, owns the decoder and latest frame, and clears stale images when stopped or restarted. SwiftUI starts reception only while the scene is active and stops it after the scene enters the background.
- **Verification performed:** The Debug build and all nine tests passed on the iPhone 13 Pro Simulator running iOS 26.5. An unsigned generic-iPhone build succeeded, and its generated Info.plist contains the expected bundle ID, portrait orientation, and local-network explanation. A local end-to-end run sent the 640×480 MPEG-TS fixture over UDP 5000 and visually confirmed the upper pane rendered it in the playing state while the lower pane stayed black.
- **Known limitations:** Raspberry Pi-to-physical-iPhone verification still requires the user's hardware. Audio, recording, settings, a secondary receiver, and background reception remain out of scope.
- **Relevant Swift concepts:** `ObservableObject` and `@Published` notify SwiftUI when the frame or state changes. `@StateObject` keeps the model alive across view redraws, while `scenePhase` reports foreground/background transitions.

## Decode H264 MPEG-TS video frames

- **Commit:** `Decode H264 MPEG-TS video frames`
- **Intent:** Provide a cancellable internal decoder that turns the fixed H.264/MPEG-TS input into display-ready images.
- **What changed:** Added an Objective-C FFmpeg bridge, Swift bridging header, a deterministic 640×480 MPEG-TS fixture, and tests for successful decoding, invalid input, and cancellation.
- **Important implementation details:** Decoding runs on a private serial queue. FFmpeg interrupt deadlines bound blocking opens and reads, malformed packets are skipped, all C resources have one cleanup path, UDP failures retry after a short delay, and a dispatch source coalesces pending output so only the newest BGRA `CGImage` reaches the main queue.
- **Verification performed:** The Debug build and all seven tests passed on the iPhone 13 Pro Simulator running iOS 26.5, including 640×480 decoding, invalid-input, and cancellation coverage. An unsigned Debug build and Xcode static analysis also succeeded for the generic physical-iPhone destination with no compiler warnings.
- **Known limitations:** The decoder is not connected to the SwiftUI screen yet. UDP port 5000 will be fixed by the stream model in the next checkpoint.
- **Relevant Swift concepts:** The bridging header exposes one Objective-C class to Swift. Callbacks cross back to the main queue so later UI state can be updated safely.

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
