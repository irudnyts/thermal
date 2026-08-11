import XCTest
@testable import Stream

final class StreamTests: XCTestCase {
    func testBundleIdentifier() {
        XCTAssertEqual(Bundle.main.bundleIdentifier, "com.irudnyts.stream")
    }
}
