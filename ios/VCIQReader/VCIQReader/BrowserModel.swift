import Combine
import Foundation
import WebKit

@MainActor
final class BrowserModel: ObservableObject {
    @Published private(set) var currentURL: URL = AppConfiguration.homeURL
    @Published private(set) var canGoBack = false
    @Published private(set) var canGoForward = false
    @Published private(set) var isLoading = false
    @Published private(set) var pageTitle = "VCIQ"
    @Published private(set) var errorMessage: String?

    private weak var webView: WKWebView?

    func attach(_ webView: WKWebView) {
        self.webView = webView
        sync(from: webView)
    }

    func sync(from webView: WKWebView) {
        if let url = webView.url {
            currentURL = url
        }
        canGoBack = webView.canGoBack
        canGoForward = webView.canGoForward
        isLoading = webView.isLoading
        if let title = webView.title, !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            pageTitle = title
        }
    }

    func navigationStarted(_ webView: WKWebView) {
        errorMessage = nil
        sync(from: webView)
        isLoading = true
    }

    func navigationFinished(_ webView: WKWebView) {
        errorMessage = nil
        sync(from: webView)
        isLoading = false
    }

    func navigationFailed(_ webView: WKWebView, error: Error) {
        sync(from: webView)
        isLoading = false

        let nsError = error as NSError
        if nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorCancelled {
            return
        }
        errorMessage = "页面暂时无法加载，请检查网络后重试。"
    }

    func dismissError() {
        errorMessage = nil
    }

    func goBack() {
        guard let webView, webView.canGoBack else { return }
        webView.goBack()
    }

    func goForward() {
        guard let webView, webView.canGoForward else { return }
        webView.goForward()
    }

    func goHome() {
        load(AppConfiguration.homeURL)
    }

    func reload() {
        errorMessage = nil
        webView?.reload()
    }

    func load(_ url: URL) {
        errorMessage = nil
        webView?.load(URLRequest(url: url, cachePolicy: .useProtocolCachePolicy, timeoutInterval: 30))
    }
}
