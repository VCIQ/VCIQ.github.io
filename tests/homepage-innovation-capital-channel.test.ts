import assert from "node:assert/strict";
import test from "node:test";

import {
  buildHomepageInnovationCapitalIndex,
  buildInnovationCapitalFeedProjection,
  homepageInnovationCapitalAnnotation,
  matchesHomepageInnovationCapitalChannel,
} from "../lib/homepage-innovation-capital-channel";

function watchlist() {
  return {
    asOf: "2026-09-23",
    brokers: ["中信证券", "中金公司"],
    policyThemes: ["人工智能", "具身智能", "航空航天"],
    projects: [
      {
        company: "北京星河动力航天科技股份有限公司",
        aliases: ["星河动力", "Galactic Energy"],
        broker: "中信证券",
        stage: "辅导中",
      },
    ],
  };
}

function lifecycle() {
  return {
    projects: [
      {
        company: "宇树科技股份有限公司",
        aliases: ["宇树科技", "Unitree Robotics"],
        broker: "中金公司",
        stage: "已上市",
      },
    ],
  };
}

function mature() {
  return {
    candidates: [
      {
        name: "艾利特机器人",
        aliases: ["Elite Robots"],
        financingRound: "D+轮",
      },
    ],
  };
}

function seeds() {
  return {
    brokers: [
      { name: "中信证券", aliases: ["中信证券"] },
      { name: "中金公司", aliases: ["中金公司", "CICC"] },
    ],
    institutions: [
      { name: "红杉中国", aliases: ["红杉", "红杉中国", "HongShan"] },
    ],
  };
}

function project() {
  return buildInnovationCapitalFeedProjection({
    articlesPayload: {
      generatedAt: "2026-09-23T01:00:00Z",
      articles: [
        {
          id: "tracked-project-funding",
          title: "星河动力完成新一轮融资并推进上市辅导",
          summary: "商业航天企业星河动力完成D轮融资，中信证券继续推进IPO辅导。",
          company: "星河动力",
          sector: "商业航天",
          type: "融资",
          publishedAt: "2026-09-23T00:50:00Z",
          importance: 92,
          source: {
            name: "公司官网",
            url: "https://example.com/galactic",
            level: "官方披露",
          },
        },
        {
          id: "lifecycle",
          title: "宇树科技上市后披露最新机器人量产进展",
          summary: "宇树科技公布人形机器人量产与商业化进展。",
          company: "宇树科技",
          sector: "机器人",
          type: "公司动态",
          publishedAt: "2026-09-23T00:40:00Z",
          importance: 85,
          source: {
            name: "交易所",
            url: "https://example.com/unitree",
            level: "交易所公告",
          },
        },
        {
          id: "institution-funding",
          title: "红杉中国继续投资具身智能项目",
          summary: "红杉中国参与某机器人公司D+轮融资。",
          sector: "机器人",
          type: "投资",
          publishedAt: "2026-09-23T00:30:00Z",
          importance: 80,
          source: {
            name: "投资机构官网",
            url: "https://example.com/hongshan",
            level: "投资机构官方",
          },
        },
        {
          id: "mature",
          title: "艾利特机器人完成D+轮融资",
          summary: "艾利特机器人继续扩大协作机器人产能。",
          company: "艾利特机器人",
          sector: "机器人",
          type: "融资",
          publishedAt: "2026-09-23T00:20:00Z",
          importance: 78,
          source: {
            name: "公司官网",
            url: "https://example.com/elite",
            level: "官方披露",
          },
        },
        {
          id: "broker-noise",
          title: "中信证券发布人工智能行业研究报告",
          summary: "分析AI应用趋势与行业估值。",
          sector: "AI / AGI",
          type: "研究",
          publishedAt: "2026-09-23T00:10:00Z",
          importance: 75,
          source: {
            name: "媒体",
            url: "https://example.com/broker-noise",
            level: "待交叉验证",
          },
        },
        {
          id: "generic-ai",
          title: "某AI公司发布新模型",
          summary: "模型能力提升。",
          sector: "AI / AGI",
          type: "产品",
          publishedAt: "2026-09-23T00:00:00Z",
          importance: 90,
          source: {
            name: "媒体",
            url: "https://example.com/generic-ai",
            level: "待交叉验证",
          },
        },
        {
          id: "discovery",
          sourceId: "innovation-listing-broker-01",
          title: "新锐半导体股份有限公司启动IPO辅导",
          summary: "新锐半导体进入A股IPO辅导阶段。",
          company: "新锐半导体股份有限公司",
          sector: "半导体",
          type: "IPO",
          publishedAt: "2026-09-23T00:00:00Z",
          importance: 70,
          source: {
            name: "发现源",
            url: "https://example.com/discovery",
            level: "待交叉验证",
          },
        },
      ],
    },
    rankedPayload: {
      generatedAt: "2026-09-23T01:10:00Z",
      items: [],
    },
    watchlistPayload: watchlist(),
    lifecyclePayload: lifecycle(),
    maturePayload: mature(),
    trackingSeedsPayload: seeds(),
  });
}

test("innovation projection requires tracked-object context plus a material event", () => {
  const projection = project();
  const ids = new Set(projection.items.map((item) => item.eventId));

  assert.ok(ids.has("tracked-project-funding"));
  assert.ok(ids.has("lifecycle"));
  assert.ok(ids.has("institution-funding"));
  assert.ok(ids.has("mature"));
  assert.ok(ids.has("discovery"));

  assert.equal(ids.has("broker-noise"), false);
  assert.equal(ids.has("generic-ai"), false);
});

test("projection records auditable object reasons instead of inferring listing outcomes", () => {
  const projection = project();
  const funding = projection.items.find((item) => item.eventId === "tracked-project-funding");
  const lifecycleItem = projection.items.find((item) => item.eventId === "lifecycle");
  const matureItem = projection.items.find((item) => item.eventId === "mature");

  assert.ok(funding);
  assert.ok(lifecycleItem);
  assert.ok(matureItem);

  assert.ok(funding.reasonCodes.includes("TRACKED_PROJECT"));
  assert.ok(funding.reasonCodes.includes("FUNDING_EVENT"));
  assert.equal(funding.evidenceTier, "primary");

  assert.ok(lifecycleItem.reasonCodes.includes("LIFECYCLE_PROJECT"));
  assert.ok(matureItem.reasonCodes.includes("MATURE_CANDIDATE"));
  assert.doesNotMatch(JSON.stringify(projection), /上市概率|成功率|投资评级/u);
});

test("dedicated discovery sources can enter review-oriented innovation feed without being reviewed truth", () => {
  const projection = project();
  const discovery = projection.items.find((item) => item.eventId === "discovery");

  assert.ok(discovery);
  assert.equal(discovery.evidenceTier, "discovery");
  assert.ok(discovery.reasonCodes.includes("INNOVATION_DISCOVERY_SOURCE"));
  assert.ok(discovery.reasonCodes.includes("DISCOVERED_COMPANY"));
  assert.equal(discovery.matchedObjects[0]?.type, "discovered-company");
});

test("homepage matching survives event identity merge through canonical source URL", () => {
  const projection = project();
  const index = buildHomepageInnovationCapitalIndex(projection);
  const event = {
    id: "different-id-after-merge",
    title: "星河动力完成新一轮融资并推进上市辅导",
    summary: "",
    sector: "商业航天",
    source: {
      name: "公司官网",
      url: "https://example.com/galactic",
      level: "官方披露",
    },
  };

  assert.equal(matchesHomepageInnovationCapitalChannel(event, index), true);
  assert.equal(
    homepageInnovationCapitalAnnotation(event, index)?.eventId,
    "tracked-project-funding",
  );
});
