"use client";

import { useState } from "react";

import { Section } from "@/components/common/states";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Field, NumberInput, TextArea, TextInput } from "@/components/ui/field";
import { useSavePlaybook } from "@/lib/queries";
import type { Bias, DailyPlan, DailyReview } from "@/lib/types";

/*
  SCREENS.md 8, FR-PB-02 and FR-PB-03.

  Each form initialises its state from props and is keyed on the date by its
  parent, so switching days remounts it. Copying props into state from an
  effect would cascade a render every time the query refetched.
*/

const BIASES: Array<{ value: Bias; label: string }> = [
  { value: "bullish", label: "Bullish" },
  { value: "bearish", label: "Bearish" },
  { value: "neutral", label: "Neutral" },
];

const EMOTIONS = ["calm", "anxious", "frustrated", "greedy"] as const;
const RATINGS = [1, 2, 3, 4, 5] as const;

function DoneChip({ done }: { done: boolean }) {
  return done ? <Chip tone="profit">Done</Chip> : <Chip>Not written</Chip>;
}

function RatingPicker({
  legend,
  value,
  onChange,
}: {
  legend: string;
  value: number | null;
  onChange: (rating: number) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-secondary text-slate">{legend}</legend>
      <div className="flex gap-2">
        {RATINGS.map((rating) => (
          <button
            key={rating}
            type="button"
            onClick={() => onChange(rating)}
            aria-label={`${legend} ${rating} of 5`}
            aria-pressed={value === rating}
            className={`size-11 rounded-[6px] border text-row tabular ${
              value === rating
                ? "border-graphite bg-graphite text-white"
                : "border-rule bg-sheet text-graphite hover:bg-fog"
            }`}
          >
            {rating}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function PlanForm({ date, plan }: { date: string; plan: DailyPlan | null }) {
  const save = useSavePlaybook(date);
  const [bias, setBias] = useState<Bias | null>(plan?.bias ?? null);
  const [keyLevels, setKeyLevels] = useState(plan?.key_levels ?? "");
  const [events, setEvents] = useState(plan?.events ?? "");
  const [maxLoss, setMaxLoss] = useState(plan?.max_loss ?? "");
  const [maxTrades, setMaxTrades] = useState(
    plan?.max_trades != null ? String(plan.max_trades) : "",
  );

  return (
    <Section title="Before the open" action={<DoneChip done={Boolean(plan)} />}>
      <div className="flex flex-col gap-5">
        <fieldset className="flex flex-col gap-2">
          <legend className="text-secondary text-slate">Bias</legend>
          <div className="flex gap-2">
            {BIASES.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setBias(option.value)}
                aria-pressed={bias === option.value}
              >
                <Chip tone={bias === option.value ? "selected" : "default"}>{option.label}</Chip>
              </button>
            ))}
          </div>
        </fieldset>

        <Field label="Key levels">
          {(id) => (
            <TextInput id={id} value={keyLevels} onChange={(e) => setKeyLevels(e.target.value)} />
          )}
        </Field>

        <Field label="Events">
          {(id) => <TextInput id={id} value={events} onChange={(e) => setEvents(e.target.value)} />}
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Max loss">
            {(id) => (
              <NumberInput id={id} value={maxLoss} onChange={(e) => setMaxLoss(e.target.value)} />
            )}
          </Field>
          <Field label="Max trades">
            {(id) => (
              <NumberInput
                id={id}
                inputMode="numeric"
                value={maxTrades}
                onChange={(e) => setMaxTrades(e.target.value)}
              />
            )}
          </Field>
        </div>

        <div className="flex items-center gap-3">
          <Button
            size="md"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                plan: {
                  bias,
                  key_levels: keyLevels || null,
                  events: events || null,
                  max_loss: maxLoss || null,
                  max_trades: maxTrades ? Number(maxTrades) : null,
                },
              })
            }
          >
            {save.isPending ? "Saving…" : "Save plan"}
          </Button>
          {save.isSuccess && !save.isPending && (
            <span role="status" className="text-secondary text-slate">
              Saved
            </span>
          )}
        </div>
      </div>
    </Section>
  );
}

export function ReviewForm({ date, review }: { date: string; review: DailyReview | null }) {
  const save = useSavePlaybook(date);
  const [rating, setRating] = useState<number | null>(review?.discipline_rating ?? null);
  const [emotion, setEmotion] = useState<string | null>(review?.emotion ?? null);
  const [wentWell, setWentWell] = useState(review?.went_well ?? "");
  const [toImprove, setToImprove] = useState(review?.to_improve ?? "");

  return (
    <Section title="After the close" action={<DoneChip done={Boolean(review)} />}>
      <div className="flex flex-col gap-5">
        <RatingPicker legend="Discipline" value={rating} onChange={setRating} />

        <fieldset className="flex flex-col gap-2">
          <legend className="text-secondary text-slate">How it felt</legend>
          <div className="flex flex-wrap gap-2">
            {EMOTIONS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setEmotion(value)}
                aria-pressed={emotion === value}
              >
                <Chip tone={emotion === value ? "selected" : "default"}>
                  {value[0].toUpperCase() + value.slice(1)}
                </Chip>
              </button>
            ))}
          </div>
        </fieldset>

        <Field label="What went well">
          {(id) => (
            <TextArea id={id} value={wentWell} onChange={(e) => setWentWell(e.target.value)} />
          )}
        </Field>

        <Field label="What to improve">
          {(id) => (
            <TextArea id={id} value={toImprove} onChange={(e) => setToImprove(e.target.value)} />
          )}
        </Field>

        <div className="flex items-center gap-3">
          <Button
            size="md"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                review: {
                  discipline_rating: rating,
                  emotion,
                  went_well: wentWell || null,
                  to_improve: toImprove || null,
                },
              })
            }
          >
            {save.isPending ? "Saving…" : "Save review"}
          </Button>
          {save.isSuccess && !save.isPending && (
            <span role="status" className="text-secondary text-slate">
              Saved
            </span>
          )}
        </div>
      </div>
    </Section>
  );
}
