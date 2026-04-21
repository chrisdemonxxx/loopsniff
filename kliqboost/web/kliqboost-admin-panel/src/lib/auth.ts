import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.kliqboost.store"

const ADMIN_ROLES = ["super_admin", "admin", "staff", "support"] as const
type AdminRole = (typeof ADMIN_ROLES)[number]

function isAdminRole(role: string | undefined): role is AdminRole {
  return ADMIN_ROLES.includes(role as AdminRole)
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        try {
          const headers: Record<string, string> = { "Content-Type": "application/json" }
          if (process.env.NODE_ENV !== "production") {
            headers["ngrok-skip-browser-warning"] = "1"
          }
          const res = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers,
            body: JSON.stringify({
              email: credentials?.email,
              password: credentials?.password,
            }),
          })
          if (!res.ok) return null
          const data = await res.json()
          const role: string | undefined = data.admin?.role ?? data.role
          if (!isAdminRole(role)) return null
          return {
            id: data.admin?.id ?? data.user_id,
            name: data.admin?.name ?? data.name,
            email: credentials?.email as string,
            role,
            accessToken: data.access_token,
            userType: "admin",
          }
        } catch {
          return null
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.role = (user as any).role
        token.accessToken = (user as any).accessToken
        token.userType = (user as any).userType
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        ;(session.user as any).role = token.role
        ;(session.user as any).accessToken = token.accessToken
        ;(session.user as any).userType = token.userType
      }
      return session
    },
  },
  pages: {
    signIn: "/login",
  },
})
