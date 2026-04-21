"use client"

import { useSession, signOut } from "next-auth/react"
import { useState, useEffect, useCallback } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://kliqboost-api.onrender.com"

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : undefined
}

let signingOut = false
function handleGlobal401() {
  if (typeof window === "undefined" || signingOut) return
  signingOut = true
  // Mirror client-portal: redirect to login with reason indicator
  signOut({ callbackUrl: "/login?reason=expired" }).catch(() => {
    window.location.href = "/login?reason=expired"
  })
}

export async function apiFetch<T = any>(
  path: string,
  token?: string,
  options?: RequestInit
): Promise<T> {
  const method = (options?.method || "GET").toUpperCase()
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(process.env.NODE_ENV !== "production" ? { "ngrok-skip-browser-warning": "1" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  if (method !== "GET" && method !== "HEAD") {
    const csrf = readCookie("csrf_token") || readCookie("XSRF-TOKEN") || readCookie("csrftoken")
    if (csrf) headers["X-CSRF-Token"] = csrf
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...headers, ...(options?.headers as Record<string, string>) },
    credentials: "include",
  })

  if (res.status === 401) {
    handleGlobal401()
    throw new ApiError("Session expired", 401)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(body.detail || `API error ${res.status}`, res.status)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export function useApi<T = any>(path: string | null) {
  const { data: session } = useSession()
  const token = (session?.user as any)?.accessToken as string | undefined
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    if (!token || !path) return
    setLoading(true)
    setError(null)
    try {
      const result = await apiFetch<T>(path, token)
      setData(result)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [path, token])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}

export function useApiToken() {
  const { data: session } = useSession()
  return (session?.user as any)?.accessToken as string | undefined
}

export { API_URL }
