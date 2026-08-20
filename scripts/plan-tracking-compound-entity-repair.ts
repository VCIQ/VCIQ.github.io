import rawTrackingConfig from "../config/user_tracking.json";
import { buildCurrentCompoundTrackingRepairPlan } from "../lib/tracking-compound-entity-repair-plan";
import { normalizeTrackingConfig } from "../lib/user-tracking";

const config = normalizeTrackingConfig(rawTrackingConfig);
const { audit } = buildCurrentCompoundTrackingRepairPlan(config);

console.log(JSON.stringify(audit, null, 2));
