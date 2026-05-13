import { redirect } from "next/navigation";

/** 预警已合并到活动页 */
export default function AlertsPageRedirect() {
  redirect("/activity");
}
