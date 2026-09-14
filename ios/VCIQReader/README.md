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

- `vciq.github.io`：在当前 `WKWebView` 内导航。
- `https/http` 外部域名：调用系统打开，默认进入 Safari / 默认浏览器。
- `mailto:` / `tel:`：交给系统处理。

这样可以避免把第三方新闻站、登录页或支付/下载页面强行嵌在 VCIQ 的 WebView 里。

## TestFlight 前还需要完成

V0.2 先完成可运行的原生阅读壳，不在仓库里伪造最终 App Store 素材。进入 TestFlight 前还需要：

1. 准备正式的 **1024×1024 App Icon** 并添加到 `Assets.xcassets/AppIcon.appiconset`。
2. 确认 Apple Developer Team 与最终 Bundle Identifier。
3. 在 App Store Connect 创建 App 记录。
4. Archive 后通过 Xcode Organizer 上传 TestFlight 构建。
5. 用至少一台真实 iPhone 验证：登录状态、收藏、分享、站外链接、横竖屏、弱网/断网恢复。

> 公开提交 App Store 之前还应补充足够的原生价值（例如原生推送、Share Extension、阅读队列或离线收藏）。单纯网站包装壳可能面临 Minimum Functionality 审核风险；TestFlight 内测不以此作为当前阻塞项。
