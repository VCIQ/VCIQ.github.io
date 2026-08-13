export const SITE_SHARE_IMAGE_SIZE = {
  width: 1200,
  height: 630,
};

export const SITE_SHARE_IMAGE_ALT =
  "丽泽路1号：围绕核心技术、核心赛道、核心人物与核心公司的一级市场科技研究";

export function SiteShareImage() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "72px 82px",
        background: "#f3f2ec",
        color: "#15201c",
        fontFamily: "sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "2px solid #ccd2ca",
          paddingBottom: "30px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
          <div
            style={{
              width: "68px",
              height: "68px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "2px solid #47755a",
              color: "#275e3d",
              fontSize: "22px",
              fontWeight: 800,
              letterSpacing: "0.12em",
            }}
          >
            LZ
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "31px", fontWeight: 700 }}>丽泽路1号</span>
            <span style={{ color: "#56635d", fontSize: "18px", letterSpacing: "0.16em" }}>
              PRIMARY MARKET RESEARCH
            </span>
          </div>
        </div>
        <span style={{ color: "#47755a", fontSize: "20px", fontWeight: 700 }}>VCIQ</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", maxWidth: "930px" }}>
        <span style={{ color: "#47755a", fontSize: "22px", fontWeight: 700 }}>
          中美双轨 · 公开信源 · 可追溯研究
        </span>
        <span style={{ marginTop: "18px", fontSize: "61px", fontWeight: 700, lineHeight: 1.18 }}>
          以公开证据组织可复核的科技研究
        </span>
        <span style={{ marginTop: "22px", color: "#56635d", fontSize: "27px", lineHeight: 1.5 }}>
          核心技术 · 核心赛道 · 核心人物 · 核心公司
        </span>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "#56635d",
          fontSize: "18px",
        }}
      >
        <span>事实、计算与判断分层呈现</span>
        <span>vciq.github.io</span>
      </div>
    </div>
  );
}
