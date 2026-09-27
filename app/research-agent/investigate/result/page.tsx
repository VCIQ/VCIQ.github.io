import NativeResearchResultClient from "./native-research-result-client";

export const metadata = {
  title: "Native Research Result · VCIQ",
  description: "查看指定 VCIQ 事件是否已经形成证据绑定的 Research Agent 研究结果。",
};

export default function NativeResearchResultPage() {
  return <NativeResearchResultClient />;
}
