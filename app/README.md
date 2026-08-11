# Stream

Stream is an iPhone application that will display an H.264/MPEG-TS camera stream received over UDP. It currently shows two portrait camera placeholders; the upper pane is reserved for the primary stream and the lower pane for a future secondary camera.

## Requirements

- macOS with Xcode 26.6 or another Xcode version capable of targeting iOS 17
- An iPhone 13 Pro Simulator running iOS 17 or newer for reference-device testing

Install Xcode from the Mac App Store or [Apple Developer downloads](https://developer.apple.com/download/all/), open it once, accept its license, and allow it to install the iOS platform components. The FFmpeg helper uses only tools supplied by macOS and Xcode: `clang`, the iOS SDKs, `curl`, `make`, and `tar`. Homebrew and CocoaPods are not required.

## Open and run

1. Open `Stream.xcodeproj` in Xcode.
2. Select the `Stream` scheme.
3. Select the iPhone 13 Pro Simulator.
4. Choose **Product > Run**.

The app opens in portrait and displays two equal, black 4:3 panes. The upper pane says “Listening on UDP 5000”.

The iPhone 13 Pro is the project's reference device. The app remains compatible with other iPhones running iOS 17 or newer.

## Build the FFmpeg dependency

FFmpeg is needed to receive UDP, demultiplex MPEG-TS, decode H.264, and convert frames for display. Apple provides H.264 decoding APIs, but not a complete UDP/MPEG-TS receiver; replacing FFmpeg would require a custom transport-stream parser and substantially more code.

The checked-in helper downloads the official FFmpeg 8.1.2 source and builds static arm64 libraries for both iPhone devices and Apple-silicon Simulators. Its configuration excludes command-line programs, encoders, GPL/nonfree code, and unrelated formats.

Run this checkpoint yourself:

```sh
cd /Users/irudnyts/Documents/projects/thermal/app
./Scripts/build_ffmpeg_ios.sh
```

The script replaces only these generated, Git-ignored paths:

- `app/Vendor/FFmpeg/.build/`
- `app/Vendor/FFmpeg/FFmpeg.xcframework/`

Expected output:

```text
Created app/Vendor/FFmpeg/FFmpeg.xcframework
```

The Xcode project does not link this output yet. After the command finishes, confirm the generated framework exists before continuing to the linking checkpoint.
