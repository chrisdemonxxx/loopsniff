import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.adflux.store"

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
          const res = await fetch(`${API_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "ngrok-skip-browser-warning": "1" },
            body: JSON.stringify({
              email: credentials?.email,
              password: credentials?.password,
            }),
          })
          if (!res.ok) return null
          const data = await res.json()
          if (data.user_type !== "admin") return null
          return {
            id: data.user_id,
            name: data.name,
            email: credentials?.email as string,
            role: "super_admin",
            accessToken: data.access_token,
            userType: data.user_type,
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
