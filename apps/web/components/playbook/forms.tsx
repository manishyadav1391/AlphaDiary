"use client";

import { useState } from "react";
import { Check, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, NumberInput, TextArea, TextInput } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { celebrate } from "@/lib/motion";
import { useSavePlaybook } from "@/lib/queries";
import type { Bias, DailyPlan, DailyReview, PlanVersusActual } from "@/lib/types";
import { cn } from "@/lib/utils";

const BIASES: Array<{ value: Bias; label: string; icon: string }> = [
  { value: "bullish", label: "Bullish", icon: "↗" },
  { value: "bearish", label: "Bearish", icon: "↘" },
  { value: "neutral", label: "Neutral", icon: "↔" },
];

const EMOTIONS = [
  { value: "calm", label: "Calm", tone: "calm" as const },
  { value: "anxious", label: "Anxious", tone: "anxious" as const },
  { value: "frustrated", label: "Frustrated", tone: "frustrated" as const },
  { value: "greedy", label: "Greedy", tone: "greedy" as const },
];

const RATINGS = [
  { value: 1, label: "Off the rails" },
  { value: 2, label: "Slipping" },
  { value: 3, label: "Okay" },
  { value: 4, label: "Solid" },
  { value: 5, label: "Locked in" },
];

function StatusBadge({ written }: { written: boolean }) {
  if (written) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-profit/40 bg-profit-bg px-3 py-1 text-label font-medium text-profit shadow-[0_0_12px_rgba(52,211,153,0.2)]">
        <Check size={13} strokeWidth={2.5} />
        <span>Written</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-glass-border bg-glass-1 px-3 py-1 text-label font-medium text-text-2">
      <span className="size-1.5 rounded-full border border-text-2" />
      <span>Not written</span>
    </span>
  );
}

/*
  Design spec §9.3:
  Discipline rating (1–5)
  Five glass tiles. Selecting N fills tiles 1..N in a rising violet gradient.
  Selecting 5 triggers a sparkle burst.
*/
function DisciplineRating({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (rating: number) => void;
}) {
  const selectedLabel = value ? RATINGS.find((r) => r.value === value)?.label : "Not rated";

  const handleSelect = (rating: number) => {
    onChange(rating);
    if (rating === 5) {
      void celebrate({ x: 0.5, y: 0.6 }, "sm");
    }
  };

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <span className="text-label uppercase tracking-wider text-text-2 font-medium">
          Discipline
        </span>
        <span className="text-caption font-semibold text-violet-300">{selectedLabel}</span>
      </div>

      <div className="flex gap-2.5" role="radiogroup" aria-label="Discipline rating">
        {RATINGS.map((r) => {
          const isFilled = value !== null && r.value <= value;
          const isSelected = value === r.value;

          return (
            <button
              key={r.value}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => handleSelect(r.value)}
              className={cn(
                "glass relative flex size-12 items-center justify-center rounded-[12px] font-mono text-h3 font-bold transition-all duration-200 select-none",
                isFilled
                  ? "border-violet-500/50 bg-[linear-gradient(180deg,rgba(139,92,246,0.3)_0%,rgba(109,40,217,0.15)_100%)] text-white shadow-[0_0_16px_rgba(139,92,246,0.35)]"
                  : "bg-glass-1 text-text-2 hover:bg-glass-2 hover:text-text-0",
                isSelected && "scale-105 border-violet-400 ring-2 ring-violet-400/40",
              )}
            >
              {r.value}
              {r.value === 5 && isFilled && (
                <Sparkles size={11} className="absolute top-1 right-1 text-violet-300" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/*
  Design spec §10.4 Card 1: Before the open
*/
export function PlanForm({
  date,
  plan,
  actual,
}: {
  date: string;
  plan: DailyPlan | null;
  actual?: PlanVersusActual;
}) {
  const save = useSavePlaybook(date);
  const toast = useToast();
  const [bias, setBias] = useState<Bias | null>(plan?.bias ?? null);
  const [keyLevels, setKeyLevels] = useState(plan?.key_levels ?? "");
  const [events, setEvents] = useState(plan?.events ?? "");
  const [maxLoss, setMaxLoss] = useState(plan?.max_loss ?? "");
  const [maxTrades, setMaxTrades] = useState(
    plan?.max_trades != null ? String(plan.max_trades) : "",
  );
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = async () => {
    try {
      await save.mutateAsync({
        plan: {
          bias,
          key_levels: keyLevels || null,
          events: events || null,
          max_loss: maxLoss || null,
          max_trades: maxTrades ? Number(maxTrades) : null,
        },
      });
      setSavedSuccess(true);
      toast("Plan saved successfully");
      setTimeout(() => setSavedSuccess(false), 2000);
    } catch {
      toast("Failed to save plan", { variant: "error" });
    }
  };

  return (
    <div className="glass flex flex-col gap-6 p-6 md:p-8">
      <div className="flex items-center justify-between border-b border-glass-border/60 pb-4">
        <h2 className="text-h2 font-bold text-text-0">Before the open</h2>
        <StatusBadge written={Boolean(plan) || savedSuccess} />
      </div>

      <div className="flex flex-col gap-5">
        {/* Bias selector */}
        <div className="flex flex-col gap-2">
          <span className="text-label uppercase tracking-wider text-text-2 font-medium">
            Market Bias
          </span>
          <div className="flex flex-wrap gap-2.5">
            {BIASES.map((option) => {
              const isSelected = bias === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setBias(option.value)}
                  className="rounded-full transition-transform active:scale-95"
                >
                  <Chip
                    tone={
                      isSelected
                        ? option.value === "bullish"
                          ? "bullish"
                          : option.value === "bearish"
                            ? "bearish"
                            : "neutral"
                        : "default"
                    }
                    className="h-9 px-4 text-body cursor-pointer"
                  >
                    <span>{option.icon}</span>
                    <span>{option.label}</span>
                  </Chip>
                </button>
              );
            })}
          </div>
        </div>

        {/* Key levels */}
        <Field label="Key levels" hint="Support, resistance, opening range boundaries">
          {(id) => (
            <TextInput
              id={id}
              value={keyLevels}
              placeholder="e.g. 24,350 support · 24,600 resistance"
              onChange={(e) => setKeyLevels(e.target.value)}
            />
          )}
        </Field>

        {/* Events */}
        <Field label="Events / Catalysts">
          {(id) => (
            <TextInput
              id={id}
              value={events}
              placeholder="e.g. RBI policy 10:00, Nifty weekly expiry"
              onChange={(e) => setEvents(e.target.value)}
            />
          )}
        </Field>

        {/* Max loss and Max trades (2-col grid) */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Field label="Max loss limit">
              {(id) => (
                <NumberInput
                  id={id}
                  prefix="₹"
                  value={maxLoss}
                  placeholder="e.g. 5000"
                  onChange={(e) => setMaxLoss(e.target.value)}
                />
              )}
            </Field>
            {actual && actual.max_loss && (
              <div className="flex items-center justify-between text-[11px] text-text-2">
                <span>Current day P&L: ₹{actual.net_pnl}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Field label="Max trades limit">
              {(id) => (
                <NumberInput
                  id={id}
                  value={maxTrades}
                  placeholder="e.g. 6"
                  onChange={(e) => setMaxTrades(e.target.value)}
                />
              )}
            </Field>
            {actual && actual.max_trades !== null && (
              <div className="flex items-center justify-between text-[11px] text-text-2">
                <span>Taken: {actual.trades_taken} / {actual.max_trades}</span>
              </div>
            )}
          </div>
        </div>

        {/* Save button — ALWAYS has clear, high-contrast visible text! */}
        <div className="mt-2 flex items-center justify-between pt-2">
          <Button
            variant="primary"
            size="md"
            loading={save.isPending}
            onClick={handleSave}
            className="w-full sm:w-auto"
          >
            {savedSuccess ? (
              <>
                <Check size={16} strokeWidth={2.5} />
                <span>Plan saved</span>
              </>
            ) : (
              <span>Save plan</span>
            )}
          </Button>

          <span className="hidden text-caption text-text-disabled sm:inline">
            Press ⌘+Enter to save
          </span>
        </div>
      </div>
    </div>
  );
}

/*
  Design spec §10.4 Card 2: After the close
*/
export function ReviewForm({
  date,
  review,
}: {
  date: string;
  review: DailyReview | null;
}) {
  const save = useSavePlaybook(date);
  const toast = useToast();
  const [rating, setRating] = useState<number | null>(review?.discipline_rating ?? null);
  const [emotion, setEmotion] = useState<string | null>(review?.emotion ?? null);
  const [wentWell, setWentWell] = useState(review?.went_well ?? "");
  const [toImprove, setToImprove] = useState(review?.to_improve ?? "");
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = async () => {
    try {
      await save.mutateAsync({
        review: {
          discipline_rating: rating,
          emotion,
          went_well: wentWell || null,
          to_improve: toImprove || null,
        },
      });
      setSavedSuccess(true);
      toast("Review saved successfully");

      // Confetti celebration if Discipline rating >= 4 (spec §11.6 trigger 3)
      if (rating && rating >= 4) {
        void celebrate({ x: 0.5, y: 0.7 }, "md");
      }

      setTimeout(() => setSavedSuccess(false), 2000);
    } catch {
      toast("Failed to save review", { variant: "error" });
    }
  };

  return (
    <div className="glass flex flex-col gap-6 p-6 md:p-8">
      <div className="flex items-center justify-between border-b border-glass-border/60 pb-4">
        <h2 className="text-h2 font-bold text-text-0">After the close</h2>
        <StatusBadge written={Boolean(review) || savedSuccess} />
      </div>

      <div className="flex flex-col gap-5">
        {/* Discipline Rating 1-5 */}
        <DisciplineRating value={rating} onChange={setRating} />

        {/* Emotion / How it felt */}
        <div className="flex flex-col gap-2">
          <span className="text-label uppercase tracking-wider text-text-2 font-medium">
            How it felt
          </span>
          <div className="flex flex-wrap gap-2.5">
            {EMOTIONS.map((item) => {
              const isSelected = emotion === item.value;
              return (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setEmotion(item.value)}
                  className="rounded-full transition-transform active:scale-95"
                >
                  <Chip
                    tone={isSelected ? item.tone : "default"}
                    className="h-9 px-4 text-body cursor-pointer"
                  >
                    {item.label}
                  </Chip>
                </button>
              );
            })}
          </div>
        </div>

        {/* What went well */}
        <Field label="What went well">
          {(id) => (
            <TextArea
              id={id}
              value={wentWell}
              placeholder="Followed risk limits, waited for confirmation..."
              onChange={(e) => setWentWell(e.target.value)}
              className="focus:border-profit/60 focus:ring-profit/30"
            />
          )}
        </Field>

        {/* What to improve */}
        <Field label="What to improve">
          {(id) => (
            <TextArea
              id={id}
              value={toImprove}
              placeholder="Exited early, chased opening candle..."
              onChange={(e) => setToImprove(e.target.value)}
              className="focus:border-warn/60 focus:ring-warn/30"
            />
          )}
        </Field>

        {/* Save button — ALWAYS has clear, high-contrast visible text! */}
        <div className="mt-2 flex items-center justify-between pt-2">
          <Button
            variant="primary"
            size="md"
            loading={save.isPending}
            onClick={handleSave}
            className="w-full sm:w-auto"
          >
            {savedSuccess ? (
              <>
                <Check size={16} strokeWidth={2.5} />
                <span>Review saved</span>
              </>
            ) : (
              <span>Save review</span>
            )}
          </Button>

          <span className="hidden text-caption text-text-disabled sm:inline">
            Press ⌘+Enter to save
          </span>
        </div>
      </div>
    </div>
  );
}
