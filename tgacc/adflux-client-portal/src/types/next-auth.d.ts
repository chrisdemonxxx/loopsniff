import "next-auth"

declare module "next-auth" {
  interface Session {
    user: {
      id?: string
      name?: string | null
      email?: string | null
      image?: string | null
      role?: string
      accessToken?: string
      userType?: string
      clientId?: string
    }
  }

  interface User {
    role?: string
    accessToken?: string
    userType?: string
    clientId?: string
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: string
    accessToken?: string
    userType?: string
    clientId?: string
  }
}
