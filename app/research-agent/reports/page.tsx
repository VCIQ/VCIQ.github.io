import NativeResearchReportsPanel from "../native-research-reports-panel";

export const metadata = { title: "专题深研报告库 · VCIQ", description: "事件级研究草稿、证据不足记录和生成状态；与每日简报分开展示。" };

export default function NativeResearchArchivePage() {
  return <main className="page-shell subpage"><NativeResearchReportsPanel archive /></main>;
}
