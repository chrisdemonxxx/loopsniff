import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { API_URL, USE_NGROK_HEADER, isAdminRole, LOGIN_PATH } from "./config"

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
          if (USE_NGROK_HEADER) {
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
          if (!res.ok) {
            console.error(`[authorize] POST /auth/login → ${res.status}`)
            return null
          }
          const data = await res.json()
          const role: string | undefined = data.admin?.role ?? data.role
          if (!isAdminRole(role)) {
            console.error(`[authorize] Role not admin: ${role}`)
            return null
          }
          return {
            id: data.admin?.id ?? data.user_id,
            name: data.admin?.name ?? data.name,
            email: credentials?.email as string,
            role,
            accessToken: data.access_token,
            userType: "admin",
          }
        } catch (err) {
          console.error("[authorize] Unexpected error:", err)
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
    signIn: LOGIN_PATH,
  },
  trustHost: true,
})
