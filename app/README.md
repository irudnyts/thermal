# Stream

Stream is a landscape-right-only iPhone application that displays the 1280×560 H.264/MPEG-TS composite produced by `scripts/camera_sender_two_cameras.py` and received on UDP port 5000. The complete side-by-side camera image and its burned-in telemetry footer are shown aspect-fit, with black letterboxing when the screen has a different aspect ratio.

## Requirements

- macOS with Xcode 26.6 or another Xcode version capable of targeting iOS 17
- An iPhone 13 Pro Simulator running iOS 17 or newer for reference-device testing
- An iPhone running iOS 17 or newer and an Apple account for device signing
- The existing Raspberry Pi camera sender on the same Wi-Fi network as the iPhone

Install Xcode from the Mac App Store or [Apple Developer downloads](https://developer.apple.com/download/all/), open it once, accept its license, and allow it to install the iOS platform components. The FFmpeg helper uses only tools supplied by macOS and Xcode: `clang`, the iOS SDKs, `curl`, `make`, and `tar`. Homebrew and CocoaPods are not required.

## Open and run

1. Open `Stream.xcodeproj` in Xcode.
2. Select the `Stream` scheme.
3. Select the iPhone 13 Pro Simulator.
4. Choose **Product > Run**.

The app opens in landscape right and displays one black stream area with “Listening on UDP 5000”. Listening, reconnecting, and error statuses remain visible; the app hides its status while video is playing so it does not cover the sender's telemetry.

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

The Xcode project links this generated framework as a static library. Re-run the helper whenever the ignored `Vendor/FFmpeg/FFmpeg.xcframework` directory is missing.

## Run with the Raspberry Pi

1. Open `/Users/irudnyts/Documents/projects/thermal/app/Stream.xcodeproj` in Xcode.
2. Select the `Stream` target, open **Signing & Capabilities**, and choose your Personal Team.
3. Connect the iPhone to the Mac, enable Developer Mode when prompted, and select that iPhone as Xcode's run destination.
4. On the iPhone, open **Settings > Wi-Fi**, tap the information button beside the connected network, and note the iPhone's IPv4 address.
5. Configure `.env` in the repository root on the Raspberry Pi:

   ```text
   MAC_IP=<iphone-wifi-ip>
   PORT=5000
   ```

6. Run Stream from Xcode. Accept the Local Network permission prompt and leave the app active.
7. From the repository root, start `python3 scripts/camera_sender_two_cameras.py` using the sender's existing Python environment.

The status should move through listening or reconnecting and then disappear when playback begins. Both camera images and the complete telemetry footer should remain visible. Stream stops its receiver when sent to the background and starts listening again when it becomes active.

If no video appears, confirm both devices are on the same Wi-Fi network, recheck the iPhone address in `.env`, verify UDP port 5000 is not blocked, and start the app before the sender.
