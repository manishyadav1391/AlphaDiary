import { redirect } from "next/navigation";

/** Home lives at `/` (SCREENS.md 2); this keeps `/dashboard` links working. */
export default function DashboardRedirect() {
  redirect("/");
}
