"use client"

import { useState } from "react"
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { cn } from "cn"

import { Button } from "../primitives/button"
import {
  buildJalaliMonth,
  compareJalaliParts,
  formatJalaliParts,
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_INITIALS,
  shiftJalaliMonth,
  toJalaliParts,
  type JalaliParts,
} from "../../lib/jalali"
import { toPersianDigits } from "../../lib/number"

export type JalaliRangeCalendarProps = {
  /** Inclusive start of the selected range. */
  from: JalaliParts | null
  /** Inclusive end of the selected range. */
  to: JalaliParts | null
  onSelect: (day: JalaliParts) => void
  /** Latest selectable day; defaults to no upper bound. */
  maxDate?: JalaliParts | null
  className?: string
}

function sameDay(a: JalaliParts | null, b: JalaliParts | null): boolean {
  return a !== null && b !== null && compareJalaliParts(a, b) === 0
}

function inRange(
  day: JalaliParts,
  from: JalaliParts | null,
  to: JalaliParts | null
): boolean {
  return (
    from !== null &&
    to !== null &&
    compareJalaliParts(day, from) >= 0 &&
    compareJalaliParts(day, to) <= 0
  )
}

/** Jalali month grid with a Saturday-first week and a single range selection. */
export function JalaliRangeCalendar({
  from,
  to,
  onSelect,
  maxDate = null,
  className,
}: JalaliRangeCalendarProps) {
  const [today] = useState<JalaliParts>(() => toJalaliParts(new Date()))
  const [view, setView] = useState<Pick<JalaliParts, "year" | "month">>(() => {
    const anchor = from ?? today
    return { year: anchor.year, month: anchor.month }
  })
  const cells = buildJalaliMonth(view)

  function shiftMonth(delta: number) {
    setView((current) => shiftJalaliMonth(current, delta))
  }

  return (
    <div dir="rtl" className={cn("w-full select-none", className)}>
      <div className="mb-2 flex items-center justify-between gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="ماه قبل"
          onClick={() => shiftMonth(-1)}
        >
          <ChevronRightIcon />
        </Button>
        <p aria-live="polite" className="text-sm font-medium">
          {JALALI_MONTH_NAMES[view.month - 1]} {toPersianDigits(view.year)}
        </p>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="ماه بعد"
          onClick={() => shiftMonth(1)}
        >
          <ChevronLeftIcon />
        </Button>
      </div>

      <div className="grid grid-cols-7" aria-hidden="true">
        {JALALI_WEEKDAY_INITIALS.map((initial) => (
          <span
            key={initial}
            className="flex h-7 items-center justify-center text-[11px] text-muted-foreground"
          >
            {initial}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-7">
        {cells.map((day, index) => {
          if (day === null) {
            return <span key={`empty-${index}`} aria-hidden="true" />
          }
          const selected = sameDay(day, from) || sameDay(day, to)
          const disabled =
            maxDate !== null && compareJalaliParts(day, maxDate) > 0
          return (
            <button
              key={`${day.year}-${day.month}-${day.day}`}
              type="button"
              aria-pressed={selected}
              aria-label={formatJalaliParts(day)}
              disabled={disabled}
              onClick={() => onSelect(day)}
              className={cn(
                "flex h-9 w-full items-center justify-center rounded-xl text-xs transition-colors outline-none",
                "hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
                "disabled:pointer-events-none disabled:text-muted-foreground/40",
                inRange(day, from, to) && "bg-primary/10 hover:bg-primary/15",
                selected
                  ? "bg-primary font-medium text-primary-foreground hover:bg-primary"
                  : null,
                !inRange(day, from, to) && !selected && sameDay(day, today)
                  ? "ring-1 ring-primary/40"
                  : null
              )}
            >
              {toPersianDigits(day.day)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
