import type { Metadata } from "next"

export const metadata: Metadata = { title: "چهارسوق | محصولات" }

export default function ProductsLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return children
}
