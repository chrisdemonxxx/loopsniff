import { NextResponse } from "next/server"
import { auth } from "@/lib/auth"

const ADMIN_ROLES = ["super_admin", "admin", "staff", "support"]

// Obfuscated path gate: when ADMIN_REQUIRED_PATH_PREFIX is set, any request whose
// pathname does not start with that prefix is answered with a flat 404 (no redirect,
// no hint that an admin app lives here). The login + dashboard routes must live under
// this prefix when set (e.g. ADMIN_REQUIRED_PATH_PREFIX=/_internal/console-7f3a means
// the login page is /_internal/console-7f3a/login).
const REQUIRED_PREFIX = (process.env.ADMIN_REQUIRED_PATH_PREFIX ?? "").trim()

function stripPrefix(pathname: string): string {
  if (!REQUIRED_PREFIX) return pathname
  if (pathname === REQUIRED_PREFIX) return "/"
  if (pathname.startsWith(REQUIRED_PREFIX + "/")) {
    return pathname.slice(REQUIRED_PREFIX.length) || "/"
  }
  return pathname
}

export default auth((req) => {
  const pathname = req.nextUrl.pathname

  if (REQUIRED_PREFIX) {
    const isUnderPrefix =
      pathname === REQUIRED_PREFIX || pathname.startsWith(REQUIRED_PREFIX + "/")
    // NextAuth's own callback routes must stay reachable for the session cookie to work.
    const isAuthRoute = pathname.startsWith("/api/auth")
    if (!isUnderPrefix && !isAuthRoute) {
      return new NextResponse("Not Found", { status: 404 })
    }
  }

  const logical = stripPrefix(pathname)
  const isLoggedIn = !!req.auth
  const isLoginPage = logical.startsWith("/login")
  const isAuthRoute = pathname.startsWith("/api/auth")

  if (isAuthRoute) return

  const loginUrl = new URL(
    `${REQUIRED_PREFIX}/login`.replace(/\/+/g, "/") || "/login",
    req.nextUrl.origin,
  )
  const dashUrl = new URL(
    `${REQUIRED_PREFIX}/dashboard`.replace(/\/+/g, "/") || "/dashboard",
    req.nextUrl.origin,
  )

  if (!isLoggedIn && !isLoginPage) {
    return Response.redirect(loginUrl)
  }

  if (isLoggedIn && isLoginPage) {
    return Response.redirect(dashUrl)
  }

  if (isLoggedIn && !isLoginPage) {
    const role = req.auth?.user?.role as string | undefined
    if (!role || !ADMIN_ROLES.includes(role)) {
      return Response.redirect(loginUrl)
    }
  }
})

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
