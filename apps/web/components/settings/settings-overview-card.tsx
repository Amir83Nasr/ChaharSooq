import Link from "next/link"
import { ArrowUpRight, type LucideIcon } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/primitives/card"

type SettingsOverviewCardProps = {
  href: string
  icon: LucideIcon
  title: string
  description: string
  summary: string
}

/** Entry card on the settings overview that leads to one settings subpage. */
export function SettingsOverviewCard({
  href,
  icon: Icon,
  title,
  description,
  summary,
}: SettingsOverviewCardProps) {
  return (
    <Link
      href={href}
      className="group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-[border-color,box-shadow] group-hover:border-primary/40 group-hover:shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon className="size-4" aria-hidden="true" />
            {title}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-sm leading-6 text-muted-foreground">{summary}</p>
          <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
            مشاهده و ویرایش
            <ArrowUpRight className="size-4" aria-hidden="true" />
          </span>
        </CardContent>
      </Card>
    </Link>
  )
}
