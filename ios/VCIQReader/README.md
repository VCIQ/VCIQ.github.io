# VCIQ iOS Reader

VCIQ 的原生 iPhone/iPad 阅读壳。它保留 `https://vciq.github.io/` 作为唯一内容源，不复制现有研究、推荐、收藏或反馈业务逻辑。

## 当前能力（V0.2）

- SwiftUI + `WKWebView`
- 站内导航保持在 App 内
- 新闻、报告等站外链接交给系统浏览器
- 原生返回 / 前进 / 首页 / 刷新 / 分享 / Safari 按钮
- 下拉刷新
- 加载进度提示
- 网络错误提示与重试
- `WKWebView` WebContent 进程异常后自动恢复
- 使用默认持久化 Website Data Store，保留 Cookie 和 Web 会话
- iPhone / iPad，横竖屏均支持
- 正式 1024×1024 VCIQ App Icon（RGB、无透明通道）

## 生成 Xcode 工程

工程描述使用 [XcodeGen](https://github.com/yonaskolb/XcodeGen)，避免手工维护容易产生冲突的 `project.pbxproj`。

```bash
cd ios/VCIQReader
brew install xcodegen
xcodegen generate
open VCIQReader.xcodeproj
```

要求：

- macOS
- Xcode 16 或更新版本
- iOS 17.0 或更新版本

## 真机运行

1. 在 Xcode 中选择 `VCIQReader` target。
2. 打开 **Signing & Capabilities**，选择自己的 Apple Developer Team。
3. 如果 `io.vciq.reader` 已被其他账号占用，将 Bundle Identifier 改成你账号下唯一的值。
4. 连接 iPhone，在顶部设备列表中选择该 iPhone。
5. 点击 Run。

无需配置额外 API Key。App 直接读取正式站点 `https://vciq.github.io/`。

## 导航边界

- `https://vciq.github.io`：在当前 `WKWebView` 内导航。
- 其它 `https/http` 域名：调用系统打开，默认进入 Safari / 默认浏览器。
- `mailto:` / `tel:`：交给系统处理。

这样可以避免把第三方新闻站、登录页或支付/下载页面强行嵌在 VCIQ 的 WebView 里。

## 自动编译验证

仓库包含 `.github/workflows/ios-test.yml`。当 iOS 工程变更时，它会在 macOS runner 上：

1. 校验 `Info.plist`；
2. 用 XcodeGen 生成 `.xcodeproj`；
3. 使用 `xcodebuild` 对 iOS Simulator target 做无签名编译。

这能提前发现 Swift / WebKit / asset catalog / Xcode 工程配置错误，但不能替代真实 iPhone 上的交互、登录态和弱网验收。

## TestFlight 前还需要完成

源码与 App Icon 可以在仓库内准备；以下步骤依赖实际 Apple Developer / App Store Connect 账号，因此进入 TestFlight 前还需要：

1. 确认 Apple Developer Team 与最终 Bundle Identifier。
2. 在 App Store Connect 创建 App 记录。
3. Archive 后通过 Xcode Organizer 上传 TestFlight 构建。
4. 用至少一台真实 iPhone 验证：登录状态、收藏、分享、站外链接、横竖屏、弱网/断网恢复。

> 公开提交 App Store 之前还应补充足够的原生价值（例如原生推送、Share Extension、阅读队列或离线收藏）。单纯网站包装壳可能面临 Minimum Functionality 审核风险；TestFlight 内测不以此作为当前阻塞项。
