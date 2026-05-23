import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import { LOGIN_PATH, DASHBOARD_PATH } from "@/lib/config"

export default async function Home() {
  const session = await auth()
  redirect(session ? DASHBOARD_PATH : LOGIN_PATH)
}
