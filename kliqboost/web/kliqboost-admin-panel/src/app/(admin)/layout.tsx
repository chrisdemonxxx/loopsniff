import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"
import { AdminShell } from "@/components/layout/admin-shell"
import { isAdminRole, LOGIN_PATH } from "@/lib/config"

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const session = await auth()
  if (!session) redirect(LOGIN_PATH)

  // Defense-in-depth: middleware also checks this, but every admin page
  // must verify the session role at render time too.
  const role = (session.user as { role?: string } | undefined)?.role
  if (!isAdminRole(role)) redirect(`${LOGIN_PATH}?reason=forbidden`)

  return <AdminShell>{children}</AdminShell>
}
