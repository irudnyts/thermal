import XCTest

final class StreamUITests: XCTestCase {
    func testCameraPaneLayout() {
        XCUIDevice.shared.orientation = .landscapeRight
        let app = XCUIApplication()
        app.launch()

        let primaryPane = app.otherElements["primaryCameraPane"]
        let secondaryPane = app.otherElements["secondaryCameraPane"]

        XCTAssertTrue(primaryPane.waitForExistence(timeout: 5))
        XCTAssertFalse(secondaryPane.exists)
        let status = app.staticTexts["streamStatus"]
        XCTAssertTrue(status.exists)
        XCTAssertFalse(status.label.isEmpty)
        XCTAssertGreaterThan(primaryPane.frame.width, primaryPane.frame.height)
        XCTAssertGreaterThan(
            app.windows.firstMatch.frame.width,
            app.windows.firstMatch.frame.height
        )

        primaryPane.tap()
        XCTAssertTrue(
            app.staticTexts["captureStatus"].waitForExistence(timeout: 3)
        )
        XCTAssertEqual(app.staticTexts["captureStatus"].label, "CAPTURE sent")
    }
}
