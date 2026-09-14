import Foundation

enum AppConfiguration {
    static let homeURL = URL(string: "https://vciq.github.io/")!
    static let allowedHost = "vciq.github.io"

    static func isInternal(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https" else {
            return false
        }
        return url.host?.lowercased() == allowedHost
    }
}
