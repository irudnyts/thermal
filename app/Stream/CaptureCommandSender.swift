import Foundation
import Network

enum CaptureCommandError: LocalizedError {
    case missingHost
    case connectionFailed(String)

    var errorDescription: String? {
        switch self {
        case .missingHost:
            "Set PI_IP in .env and rebuild the app"
        case .connectionFailed(let detail):
            "Capture send failed: \(detail)"
        }
    }
}

final class CaptureCommandSender {
    static let port = NWEndpoint.Port(rawValue: 5001)!
    static let command = Data("CAPTURE".utf8)

    private let host: String
    private let port: NWEndpoint.Port
    private let queue = DispatchQueue(label: "CaptureCommandSender")

    convenience init(bundle: Bundle = .main) {
        let configuredHost = bundle.object(
            forInfoDictionaryKey: "RaspberryPiHost"
        ) as? String
        self.init(host: configuredHost)
    }

    init(host: String?, port: NWEndpoint.Port = CaptureCommandSender.port) {
        let surroundingCharacters = CharacterSet.whitespacesAndNewlines.union(
            CharacterSet(charactersIn: "\"'")
        )
        self.host = host?.trimmingCharacters(in: surroundingCharacters) ?? ""
        self.port = port
    }

    func send(completion: @escaping (Result<Void, CaptureCommandError>) -> Void) {
        guard !host.isEmpty, host != "$(PI_IP)" else {
            DispatchQueue.main.async {
                completion(.failure(.missingHost))
            }
            return
        }

        let connection = NWConnection(
            host: NWEndpoint.Host(host),
            port: port,
            using: .udp
        )
        var didComplete = false

        func finish(_ result: Result<Void, CaptureCommandError>) {
            guard !didComplete else { return }
            didComplete = true
            connection.stateUpdateHandler = nil
            connection.cancel()
            DispatchQueue.main.async {
                completion(result)
            }
        }

        connection.stateUpdateHandler = { state in
            switch state {
            case .ready:
                connection.send(
                    content: Self.command,
                    completion: .contentProcessed { error in
                        if let error {
                            finish(.failure(.connectionFailed(error.localizedDescription)))
                        } else {
                            finish(.success(()))
                        }
                    }
                )
            case .waiting(let error), .failed(let error):
                finish(.failure(.connectionFailed(error.localizedDescription)))
            default:
                break
            }
        }
        connection.start(queue: queue)
    }
}
