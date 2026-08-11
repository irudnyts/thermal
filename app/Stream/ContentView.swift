import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 0) {
            CameraPane(
                accessibilityLabel: "Primary camera",
                accessibilityIdentifier: "primaryCameraPane",
                status: "Listening on UDP 5000"
            )

            CameraPane(
                accessibilityLabel: "Secondary camera",
                accessibilityIdentifier: "secondaryCameraPane"
            )

            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Color.black.ignoresSafeArea())
    }
}

private struct CameraPane: View {
    let accessibilityLabel: String
    let accessibilityIdentifier: String
    var status: String?

    var body: some View {
        ZStack {
            Color.black

            if let status {
                Text(status)
                    .foregroundStyle(.white)
                    .accessibilityIdentifier("streamStatus")
            }
        }
        .aspectRatio(4.0 / 3.0, contentMode: .fit)
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityIdentifier(accessibilityIdentifier)
    }
}
