import Combine
import CoreGraphics

@MainActor
final class CameraStreamModel: ObservableObject {
    enum StreamState: Equatable {
        case stopped
        case listening
        case playing
        case reconnecting
        case failed(String)
    }

    static let port = 5000

    @Published private(set) var frame: CGImage?
    @Published private(set) var state: StreamState = .stopped

    private let decoder = FFmpegVideoDecoder(
        url: "udp://0.0.0.0:\(CameraStreamModel.port)"
    )

    var statusText: String {
        switch state {
        case .stopped:
            "Stream paused"
        case .listening:
            "Listening on UDP \(Self.port)"
        case .playing:
            "Playing"
        case .reconnecting:
            "Reconnecting…"
        case .failed(let detail):
            "Stream error: \(detail)"
        }
    }

    func start() {
        guard !decoder.isRunning else { return }

        frame = nil
        state = .listening
        decoder.start(frameHandler: { [weak self] image in
            self?.frame = image
        }, statusHandler: { [weak self] status, detail in
            self?.receive(status: status, detail: detail)
        })
    }

    func stop() {
        decoder.stop()
        frame = nil
        state = .stopped
    }

    private func receive(status: FFmpegVideoDecoderStatus, detail: String?) {
        switch status {
        case .stopped:
            state = .stopped
        case .listening:
            state = .listening
        case .playing:
            state = .playing
        case .reconnecting:
            state = .reconnecting
        case .failed:
            state = .failed(detail ?? "Unknown decoder error")
        @unknown default:
            state = .failed("Unknown decoder status")
        }
    }
}
