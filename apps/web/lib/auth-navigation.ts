/**
 * Leave the dashboard after logout or an expired session.
 *
 * This is a full document navigation on purpose. `router.replace()` followed
 * by `router.refresh()` starts two overlapping RSC fetches, which Next 16's
 * Flight client can crash on ("chunk.reason.enqueueModel is not a function").
 * A full load also drops the client router cache, so no authenticated shell
 * survives the logout. `replace` keeps the authenticated page out of history.
 */
export function leaveToLogin(mode: "replace" | "assign" = "replace"): void {
  if (mode === "assign") window.location.assign("/login")
  else window.location.replace("/login")
}
