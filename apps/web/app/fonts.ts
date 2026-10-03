import localFont from "next/font/local"

export const iranYekanX = localFont({
  src: [
    { path: "../fonts/iran-yekan-x/IRANYekanX-Light.woff2", weight: "300" },
    { path: "../fonts/iran-yekan-x/IRANYekanX-Regular.woff2", weight: "400" },
    { path: "../fonts/iran-yekan-x/IRANYekanX-Medium.woff2", weight: "500" },
    { path: "../fonts/iran-yekan-x/IRANYekanX-DemiBold.woff2", weight: "600" },
    { path: "../fonts/iran-yekan-x/IRANYekanX-Bold.woff2", weight: "700" },
    { path: "../fonts/iran-yekan-x/IRANYekanX-ExtraBold.woff2", weight: "800" },
  ],
  variable: "--font-sans",
  display: "swap",
  preload: true,
})
