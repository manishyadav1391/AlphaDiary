"use client";

import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, TextInput } from "@/components/ui/field";
import { ApiError } from "@/lib/api";
import { useLogin } from "@/lib/queries";

/*
  SCREENS.md 1. Centred, one column, 360 px, no marketing copy. Errors sit
  under the form and name what to do; they never apologise (DESIGN.md 13).
*/

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

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [revealed, setRevealed] = useState(false);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    login.mutate(
      { email, password },
      { onSuccess: () => router.replace("/") },
    );
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-chalk px-4">
      <form onSubmit={onSubmit} className="flex w-full max-w-[360px] flex-col gap-6">
        <h1 className="text-title text-graphite">Trading journal</h1>

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
                className="absolute inset-y-0 right-0 flex w-12 items-center justify-center
                  text-slate hover:text-graphite"
              >
                {revealed ? <EyeOff size={20} aria-hidden /> : <Eye size={20} aria-hidden />}
              </button>
            </div>
          )}
        </Field>

        {login.isError && (
          <p role="alert" className="text-secondary text-loss">
            {messageFor(login.error)}
          </p>
        )}

        <Button type="submit" size="lg" disabled={login.isPending}>
          {login.isPending ? "Signing in…" : "Log in"}
        </Button>
      </form>
    </main>
  );
}
