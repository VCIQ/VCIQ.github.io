import SwiftUI

struct ContentView: View {
    @StateObject private var browser = BrowserModel()
    @Environment(\.openURL) private var openURL

    var body: some View {
        ZStack(alignment: .top) {
            VCIQWebView(model: browser)

            if browser.isLoading {
                ProgressView()
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
                    .frame(maxWidth: .infinity)
            }

            if let errorMessage = browser.errorMessage {
                errorBanner(errorMessage)
                    .padding(.horizontal, 12)
                    .padding(.top, 8)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            readerToolbar
        }
        .background(Color(uiColor: .systemBackground))
    }

    private var readerToolbar: some View {
        HStack(spacing: 4) {
            toolbarButton("chevron.backward", label: "返回", enabled: browser.canGoBack) {
                browser.goBack()
            }

            toolbarButton("chevron.forward", label: "前进", enabled: browser.canGoForward) {
                browser.goForward()
            }

            toolbarButton("house", label: "首页") {
                browser.goHome()
            }

            toolbarButton("arrow.clockwise", label: "刷新") {
                browser.reload()
            }

            ShareLink(item: browser.currentURL) {
                toolbarIcon("square.and.arrow.up", label: "分享")
            }
            .buttonStyle(.plain)

            Button {
                openURL(browser.currentURL)
            } label: {
                toolbarIcon("safari", label: "在 Safari 打开")
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 7)
        .frame(maxWidth: .infinity)
        .background(.bar)
        .overlay(alignment: .top) {
            Divider()
        }
    }

    private func toolbarButton(
        _ systemName: String,
        label: String,
        enabled: Bool = true,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            toolbarIcon(systemName, label: label)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.35)
    }

    private func toolbarIcon(_ systemName: String, label: String) -> some View {
        Image(systemName: systemName)
            .font(.system(size: 17, weight: .medium))
            .frame(maxWidth: .infinity, minHeight: 34)
            .contentShape(Rectangle())
            .accessibilityLabel(label)
    }

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "wifi.exclamationmark")
            Text(message)
                .font(.footnote)
                .frame(maxWidth: .infinity, alignment: .leading)
            Button("重试") {
                browser.reload()
            }
            .font(.footnote.weight(.semibold))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Color.secondary.opacity(0.2))
        }
    }
}
