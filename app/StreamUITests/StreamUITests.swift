import XCTest

final class StreamUITests: XCTestCase {
    func testCameraPaneLayout() {
        let app = XCUIApplication()
        app.launch()

        let primaryPane = app.otherElements["primaryCameraPane"]
        let secondaryPane = app.otherElements["secondaryCameraPane"]

        XCTAssertTrue(primaryPane.waitForExistence(timeout: 5))
        XCTAssertTrue(secondaryPane.exists)
        let status = app.staticTexts["streamStatus"]
        XCTAssertTrue(status.exists)
        XCTAssertFalse(status.label.isEmpty)
        XCTAssertEqual(primaryPane.frame.width, secondaryPane.frame.width, accuracy: 1)
        XCTAssertEqual(primaryPane.frame.height, secondaryPane.frame.height, accuracy: 1)
        XCTAssertEqual(primaryPane.frame.width / primaryPane.frame.height, 4.0 / 3.0, accuracy: 0.02)
        XCTAssertEqual(primaryPane.frame.maxY, secondaryPane.frame.minY, accuracy: 1)
    }
}
