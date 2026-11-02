"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, TextInput } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api";
import { useKiteSettings, useKiteStatus, useSaveKiteCredentials } from "@/lib/queries";
import { cn } from "@/lib/utils";

/*
  FR-KITE-01 and FR-KITE-09. The API key and secret used to be CLI-only
  (`app.cli set-kite-credentials`), which meant a fresh deployment could not be
  connected from the browser at all.

  The secret is write-only: the API never returns it, so the field is always
  blank and submitting it replaces whatever is stored.
*/
export function KiteSettings() {
  const settings = useKiteSettings();
  const status = useKiteStatus();
  const save = useSaveKiteCredentials();
  const toast = useToast();

  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [copied, setCopied] = useState(false);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    save.mutate(
      { api_key: apiKey.trim(), api_secret: apiSecret.trim() },
      {
        onSuccess: () => {
          setApiKey("");
          setApiSecret("");
          toast("Credentials saved");
        },
      },
    );
  }

  async function copyRedirect(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("Could not copy. Select the URL and copy it by hand.", { variant: "error" });
    }
  }

  if (settings.isLoading) return <Skeleton className="h-64 w-full rounded-[16px]" />;

  if (settings.isError) {
    const message =
      settings.error instanceof ApiError
        ? settings.error.message
        : "Could not load the Zerodha settings.";
    return (
      <p role="alert" className="text-body text-loss">
        {message}
      </p>
    );
  }

  const data = settings.data;
  const connected = status.data?.status === "connected";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Chip tone={connected ? "profit" : "marker"}>
          {connected ? "Connected" : "Not connected"}
        </Chip>
        {!connected && (
          <Link href="/connect" className={cn(buttonVariants({ size: "sm" }))}>
            Connect Zerodha
          </Link>
        )}
      </div>

      {/* FR-KITE-09: the exact string to paste into the Developer Console. */}
      <div className="flex flex-col gap-2">
        <p className="text-label text-text-2">Redirect URL</p>
        <p className="text-body text-text-2">
          Paste this into your Kite Connect app as the redirect URL. It must match exactly, and
          Zerodha requires HTTPS unless it is localhost.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 overflow-x-auto rounded-[10px] border border-glass-border bg-glass-1 px-3 py-2 font-mono text-mono-sm text-text-0">
            {data?.redirect_url}
          </code>
          <Button
            variant="secondary"
            size="md"
            onClick={() => data && void copyRedirect(data.redirect_url)}
          >
            {copied ? <Check size={16} aria-hidden /> : <Copy size={16} aria-hidden />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>

      <form onSubmit={onSubmit} className="flex max-w-[420px] flex-col gap-4">
        <Field
          label="API key"
          hint={
            data?.api_key_masked
              ? `Stored: ${data.api_key_masked}. Entering a new one replaces it.`
              : "From your Kite Connect app."
          }
        >
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              required
            />
          )}
        </Field>

        <Field
          label="API secret"
          hint={
            data?.has_secret
              ? "A secret is stored. It is never shown again; enter a new one to replace it."
              : "Stored encrypted and never returned by the API."
          }
        >
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              type="password"
              value={apiSecret}
              onChange={(event) => setApiSecret(event.target.value)}
              autoComplete="new-password"
              required
            />
          )}
        </Field>

        {save.isError && (
          <p role="alert" className="text-body text-loss">
            {save.error instanceof ApiError
              ? save.error.message
              : "Could not save. Check that the server is running."}
          </p>
        )}

        <Button
          type="submit"
          size="lg"
          className="self-start"
          disabled={save.isPending || !apiKey.trim() || !apiSecret.trim()}
        >
          {save.isPending ? "Saving…" : "Save credentials"}
        </Button>
      </form>
    </div>
  );
}
