import { ImportWizard } from "@/components/import/import-wizard";
import { Section } from "@/components/common/states";

/*
  FR-IMP. Lives at /import rather than /settings/import because the Settings
  shell does not exist yet, and because this is the only way to recover a
  trading day that was missed without a Zerodha login — it should be
  reachable, not buried. When Settings arrives, this becomes a redirect.
*/
export default function ImportPage() {
  return (
    <Section title="Import tradebook">
      <ImportWizard />
    </Section>
  );
}
