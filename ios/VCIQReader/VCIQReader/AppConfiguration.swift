import Foundation

enum AppConfiguration {
    static let homeURL = URL(string: "https://vciq.github.io/")!
    static let allowedHost = "vciq.github.io"

    static func isInternal(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased(),
              scheme == "https" || scheme == "http" else {
            return false
        }
        return url.host?.lowercased() == allowedHost
    }
}
