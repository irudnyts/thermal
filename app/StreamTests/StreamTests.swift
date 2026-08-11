import XCTest
@testable import Stream

final class StreamTests: XCTestCase {
    func testBundleIdentifier() {
        XCTAssertEqual(Bundle.main.bundleIdentifier, "com.irudnyts.stream")
    }

    func testPortraitIsTheOnlySupportedOrientation() {
        let orientations = Bundle.main.object(
            forInfoDictionaryKey: "UISupportedInterfaceOrientations"
        ) as? [String]

        XCTAssertEqual(orientations, ["UIInterfaceOrientationPortrait"])
    }

    func testLocalNetworkUsageDescriptionIsPresent() throws {
        let description = try XCTUnwrap(
            Bundle.main.object(forInfoDictionaryKey: "NSLocalNetworkUsageDescription") as? String
        )

        XCTAssertFalse(description.isEmpty)
    }

    func testFFmpegVersion() {
        XCTAssertEqual(FFmpegVersion.string, "8.1.2")
    }

    func testDecodes640By480MPEGTSFrame() throws {
        let fixtureURL = try XCTUnwrap(
            Bundle(for: Self.self).url(forResource: "test_640x480", withExtension: "ts")
        )
        let frameReceived = expectation(description: "Decoded a frame")
        let decoder = FFmpegVideoDecoder(url: fixtureURL.path)
        var didReceiveFrame = false

        decoder.start(frameHandler: { image in
            guard !didReceiveFrame else { return }
            didReceiveFrame = true
            XCTAssertEqual(image.width, 640)
            XCTAssertEqual(image.height, 480)
            frameReceived.fulfill()
        }, statusHandler: { _, _ in })

        wait(for: [frameReceived], timeout: 3)
        decoder.stop()
    }

    func testInvalidInputReportsFailure() {
        let failureReported = expectation(description: "Reported invalid input")
        let decoder = FFmpegVideoDecoder(url: "/path/that/does/not/exist.ts")

        decoder.start(frameHandler: { _ in
            XCTFail("Invalid input must not produce a frame")
        }, statusHandler: { status, _ in
            if status == .failed {
                failureReported.fulfill()
            }
        })

        wait(for: [failureReported], timeout: 3)
    }

    func testStopCancelsListeningPromptly() {
        let listening = expectation(description: "Started listening")
        let stopped = expectation(description: "Stopped listening")
        let decoder = FFmpegVideoDecoder(url: "udp://127.0.0.1:59999")

        decoder.start(frameHandler: { _ in }, statusHandler: { status, _ in
            if status == .listening {
                listening.fulfill()
            } else if status == .stopped {
                stopped.fulfill()
            }
        })
        wait(for: [listening], timeout: 2)

        let start = ContinuousClock.now
        decoder.stop()
        wait(for: [stopped], timeout: 1)

        XCTAssertLessThan(start.duration(to: .now), .seconds(1))
        XCTAssertFalse(decoder.isRunning)
    }

    func testCameraStreamModelStartsAndStops() async {
        await MainActor.run {
            let model = CameraStreamModel()

            XCTAssertEqual(model.state, .stopped)
            model.start()
            XCTAssertEqual(model.state, .listening)
            XCTAssertEqual(model.statusText, "Listening on UDP 5000")

            model.stop()
            XCTAssertEqual(model.state, .stopped)
            XCTAssertNil(model.frame)
        }
    }
}
