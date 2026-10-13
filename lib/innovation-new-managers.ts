import cohort from "@/config/innovation_new_managers_2026.json";
export const newManagerCohort = cohort;
export function newManagerCohortSummary(rows = cohort.managers) {
  return {
    total: rows.length,
    profilesChecked: rows.filter(row => row.registrationNumber && row.sourceUrl && row.checkedAt).length,
    afterJune5: rows.filter(row => row.registrationDate > "2026-06-05").length,
    withManagedFunds: rows.filter(row => row.listedFundCount > 0).length,
    months: Array.from({length:9}, (_, index) => {
      const month = `2026-${String(index+1).padStart(2,"0")}`;
      return {month, count:rows.filter(row => row.registrationDate.startsWith(month)).length};
    }),
  };
}
