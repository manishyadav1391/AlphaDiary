import { redirect } from "next/navigation";

/** The daily reflection is the Playbook (SCREENS.md 8). */
export default function JournalRedirect() {
  redirect("/playbook");
}
