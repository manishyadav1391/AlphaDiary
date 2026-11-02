"use client";

import { Eye, EyeOff, TrendingUp } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, TextInput } from "@/components/ui/field";
import { AuroraBackground } from "@/components/layout/aurora-background";
import { ApiError } from "@/lib/api";
import { useLogin } from "@/lib/queries";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "too_many_attempts") {
      return "Too many attempts. Try again in 15 minutes.";
    }
    if (error.isUnauthorized) return "Email or password is incorrect.";
    return error.message;
  }
  return "Could not reach the server. Check that it is running.";
}

function safeNext(value: string | null): string {
  if (!value) return "/";
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [revealed, setRevealed] = useState(false);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    login.mutate(
      { email, password },
      { onSuccess: () => router.replace(safeNext(params.get("next"))) },
    );
  }

  return (
    <main className="relative flex min-h-dvh items-center justify-center bg-bg-0 px-4 overflow-hidden">
      <AuroraBackground />

      <form
        onSubmit={onSubmit}
        className="glass glass--strong relative z-10 flex w-full max-w-[400px] flex-col gap-6 p-8 shadow-2xl backdrop-blur-2xl rounded-[24px]"
      >
        <div className="flex flex-col items-center gap-2 text-center pb-2">
          <div className="flex size-12 items-center justify-center rounded-[14px] bg-[linear-gradient(135deg,#8b5cf6_0%,#6d28d9_100%)] shadow-[0_0_24px_rgba(139,92,246,0.6)]">
            <TrendingUp className="size-6 text-white" />
          </div>
          <h1 className="text-h1 font-bold text-text-0 tracking-tight mt-2">
            Trading journal
          </h1>
          <p className="text-caption text-text-2">
            Sign in to access your journal & analytics
          </p>
        </div>

        <Field label="Email">
          {(id, describedBy) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              type="email"
              name="email"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              invalid={login.isError}
            />
          )}
        </Field>

        <Field label="Password">
          {(id, describedBy) => (
            <div className="relative">
              <TextInput
                id={id}
                aria-describedby={describedBy}
                type={revealed ? "text" : "password"}
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                invalid={login.isError}
                className="pr-12"
              />
              <button
                type="button"
                onClick={() => setRevealed((value) => !value)}
                aria-label={revealed ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 flex w-12 items-center justify-center text-text-2 hover:text-text-0"
              >
                {revealed ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
              </button>
            </div>
          )}
        </Field>

        {login.isError && (
          <p role="alert" className="rounded-[10px] bg-loss-bg/30 border border-loss/40 p-3 text-caption font-medium text-loss">
            {messageFor(login.error)}
          </p>
        )}

        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={login.isPending}
          className="w-full mt-2"
        >
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-dvh bg-bg-0" />}>
      <LoginForm />
    </Suspense>
  );
}
