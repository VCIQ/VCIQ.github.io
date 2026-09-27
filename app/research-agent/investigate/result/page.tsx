import { Suspense } from "react";
import NativeResearchResultClient from "./native-research-result-client";

export const metadata = {
  title: "Native Research Result · VCIQ",
  description: "查看指定 VCIQ 事件是否已经形成证据绑定的 Research Agent 研究结果。",
};

function NativeResearchResultFallback() {
  return <main><p>正在读取 Native Research 结果…</p></main>;
}

export default function NativeResearchResultPage() {
  return (
    <Suspense fallback={<NativeResearchResultFallback />}>
      <NativeResearchResultClient />
    </Suspense>
  );
}
