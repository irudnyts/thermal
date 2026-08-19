import SwiftUI

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var streamModel = CameraStreamModel()
    @State private var captureStatus: String?
    @State private var captureStatusID = UUID()

    private let captureSender = CaptureCommandSender()

    var body: some View {
        CameraPane(
            accessibilityLabel: "Two-camera stream",
            accessibilityIdentifier: "primaryCameraPane",
            image: streamModel.frame,
            status: streamModel.state == .playing ? nil : streamModel.statusText
        )
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
        .onTapGesture {
            sendCaptureCommand()
        }
        .overlay(alignment: .top) {
            if let captureStatus {
                Text(captureStatus)
                    .font(.footnote.monospaced())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.black.opacity(0.65), in: Capsule())
                    .padding(12)
                    .accessibilityIdentifier("captureStatus")
            }
        }
        .background(Color.black.ignoresSafeArea())
        .onAppear {
            updateStreaming(for: scenePhase)
        }
        .onChange(of: scenePhase) { _, newPhase in
            updateStreaming(for: newPhase)
        }
        .onDisappear {
            streamModel.stop()
            captureStatus = nil
        }
    }

    private func sendCaptureCommand() {
        captureSender.send { result in
            switch result {
            case .success:
                showCaptureStatus("CAPTURE sent")
            case .failure(let error):
                showCaptureStatus(error.localizedDescription)
            }
        }
    }

    private func showCaptureStatus(_ status: String) {
        let statusID = UUID()
        captureStatusID = statusID
        captureStatus = status

        Task {
            try? await Task.sleep(for: .seconds(1.5))
            guard captureStatusID == statusID else { return }
            captureStatus = nil
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
