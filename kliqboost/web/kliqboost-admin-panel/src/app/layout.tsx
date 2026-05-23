import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { auth } from "@/lib/auth"
import { Providers } from "@/components/providers"
import "./globals.css"

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "cyrillic"],
})

export const metadata: Metadata = {
  title: "Kliqboost Admin",
  description: "Kliqboost Admin Panel",
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await auth()

  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body>
        <Providers session={session}>{children}</Providers>
      </body>
    </html>
  )
}
