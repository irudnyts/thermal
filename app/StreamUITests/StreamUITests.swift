import XCTest

final class StreamUITests: XCTestCase {
    func testAppLaunches() {
        let app = XCUIApplication()
        app.launch()

        XCTAssertTrue(app.staticTexts["Stream"].waitForExistence(timeout: 5))
    }
}
