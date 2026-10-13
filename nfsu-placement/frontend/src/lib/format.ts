export const COURSES: Record<string, string> = {
  MTECH_CS: "M.Tech. CS",
  MTECH_AIDS: "M.Tech. AIDS",
  BTECH_MTECH_CSE: "B.Tech.–M.Tech. CSE",
  MSC_CS: "M.Sc. CS",
  MSC_DFIS: "M.Sc. DFIS",
};
export const OFFER_TYPES: Record<string, string> = { I: "Internship", F: "FTE", IF: "Internship + FTE" };
export const STATUS: Record<string, string> = {
  unplaced: "Unplaced",
  internship_only: "Internship only",
  fte_only: "FTE only",
  internship_plus_fte: "Internship + FTE",
};
export const KIND: Record<string, string> = {
  update: "Placement update",
  cell_event: "Placement Cell event",
  ppt: "Pre-placement talk",
  test: "Test",
  interview: "Interview",
};

export function when(iso?: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
export const lpa = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : `₹${Number(v).toFixed(2).replace(/\.00$/, "")} LPA`);
export const inr = (v: unknown) => (v === null || v === undefined ? "—" : `₹${Number(v).toLocaleString("en-IN")}`);
