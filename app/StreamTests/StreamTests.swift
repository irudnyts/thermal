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

    func testFFmpegVersion() {
        XCTAssertEqual(FFmpegVersion.string, "8.1.2")
    }
}
