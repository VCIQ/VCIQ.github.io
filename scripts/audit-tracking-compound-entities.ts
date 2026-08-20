import rawTrackingConfig from "../config/user_tracking.json";
import { inventoryCompoundTrackingEntities } from "../lib/tracking-compound-entity-inventory";
import { normalizeTrackingConfig } from "../lib/user-tracking";

const config = normalizeTrackingConfig(rawTrackingConfig);
const report = inventoryCompoundTrackingEntities(config);

console.log(JSON.stringify(report, null, 2));
