import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var streamModel = CameraStreamModel()

    var body: some View {
        CameraPane(
            accessibilityLabel: "Two-camera stream",
            accessibilityIdentifier: "primaryCameraPane",
            image: streamModel.frame,
            status: streamModel.state == .playing ? nil : streamModel.statusText
        )
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.ignoresSafeArea())
        .onAppear {
            updateStreaming(for: scenePhase)
        }
        .onChange(of: scenePhase) { _, newPhase in
            updateStreaming(for: newPhase)
        }
        .onDisappear {
            streamModel.stop()
        }
    }

    private func updateStreaming(for phase: ScenePhase) {
        switch phase {
        case .active:
            streamModel.start()
        case .background:
            streamModel.stop()
        case .inactive:
            break
        @unknown default:
            streamModel.stop()
        }
    }
}

private struct CameraPane: View {
    let accessibilityLabel: String
    let accessibilityIdentifier: String
    var image: CGImage?
    var status: String?

    var body: some View {
        ZStack {
            Color.black

            if let image {
                Image(decorative: image, scale: 1)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            if let status {
                Text(status)
                    .font(.footnote.monospaced())
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.black.opacity(0.65), in: Capsule())
                    .frame(
                        maxWidth: .infinity,
                        maxHeight: .infinity,
                        alignment: image == nil ? .center : .bottom
                    )
                    .padding(12)
                    .accessibilityIdentifier("streamStatus")
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
        .accessibilityElement(children: .contain)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityIdentifier(accessibilityIdentifier)
    }
}
