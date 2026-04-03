"use client";

import React, { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Zap, Mail, Lock, TrendingUp, Users, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { FadeIn, StaggerChildren, StaggerItem } from "@/components/motion";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    if (result?.error) {
      setError("Invalid email or password");
      toast("Invalid email or password", "error");
    } else {
      toast("Signed in successfully", "success");
      router.push("/dashboard");
      router.refresh();
    }
    setLoading(false);
  };

  return (
    <div className="flex min-h-screen bg-zinc-950">
      {/* Left panel — hidden on mobile */}
      <div className="relative hidden flex-1 items-center justify-center overflow-hidden lg:flex">
        {/* Gradient mesh background */}
        <div className="absolute inset-0">
          <div className="absolute left-1/4 top-1/4 h-96 w-96 animate-pulse rounded-full bg-emerald-500/20 blur-3xl" />
          <div className="absolute bottom-1/4 right-1/4 h-96 w-96 animate-pulse rounded-full bg-cyan-500/20 blur-3xl [animation-delay:1s]" />
          <div className="absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 animate-pulse rounded-full bg-violet-500/15 blur-3xl [animation-delay:2s]" />
        </div>

        <div className="relative z-10 max-w-md px-12">
          <FadeIn direction="up">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-500 shadow-lg shadow-blue-500/25">
                <Zap className="h-7 w-7 text-white" />
              </div>
              <span className="text-2xl font-bold text-white">
                AdFlux<span className="text-blue-400"> Media</span>
              </span>
            </div>
          </FadeIn>

          <FadeIn direction="up" delay={0.1}>
            <h2 className="text-gradient mb-3 text-3xl font-bold">
              Scale your advertising effortlessly
            </h2>
            <p className="text-zinc-400">
              Manage accounts, track spending, and optimize campaigns — all from
              one powerful dashboard.
            </p>
          </FadeIn>

          <StaggerChildren className="mt-10 space-y-4" staggerDelay={0.15}>
            {[
              { icon: TrendingUp, stat: "2.4x", desc: "Average ROAS increase" },
              { icon: Users, stat: "10K+", desc: "Active advertisers" },
              { icon: Globe, stat: "50+", desc: "Supported platforms" },
            ].map((item) => (
              <StaggerItem key={item.stat}>
                <div className="glass-card flex items-center gap-4 rounded-xl p-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-500/10">
                    <item.icon className="h-5 w-5 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-white">
                      {item.stat}
                    </p>
                    <p className="text-sm text-zinc-400">{item.desc}</p>
                  </div>
                </div>
              </StaggerItem>
            ))}
          </StaggerChildren>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="flex flex-1 items-center justify-center p-6">
        <FadeIn direction="up" className="w-full max-w-md">
          <div className="glass-card glow-blue rounded-2xl border border-zinc-800/50 p-8">
            {/* Logo for mobile */}
            <div className="mb-8 flex flex-col items-center gap-4 lg:items-start">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-500 shadow-lg shadow-blue-500/25 lg:hidden">
                <Zap className="h-8 w-8 text-white" />
              </div>
              <div className="text-center lg:text-left">
                <h1 className="text-2xl font-bold text-white">Sign in</h1>
                <p className="mt-1 text-sm text-zinc-400">
                  Welcome back — enter your credentials to continue
                </p>
              </div>
            </div>

            <StaggerChildren className="space-y-5" staggerDelay={0.08}>
              {error && (
                <StaggerItem>
                  <div className="rounded-lg border border-red-800 bg-red-900/50 px-4 py-3 text-sm text-red-300">
                    {error}
                  </div>
                </StaggerItem>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <StaggerItem>
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-zinc-300">
                      Email
                    </Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        className="border-zinc-800 bg-zinc-900/50 pl-10 focus:border-blue-500/50 focus:ring-blue-500/20"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </StaggerItem>

                <StaggerItem>
                  <div className="space-y-2">
                    <Label htmlFor="password" className="text-zinc-300">
                      Password
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                      <Input
                        id="password"
                        type="password"
                        placeholder="••••••••"
                        className="border-zinc-800 bg-zinc-900/50 pl-10 focus:border-blue-500/50 focus:ring-blue-500/20"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                </StaggerItem>

                <StaggerItem>
                  <Button
                    type="submit"
                    className="w-full bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-500/25 hover:from-blue-500 hover:to-violet-500"
                    disabled={loading}
                  >
                    {loading ? "Signing in..." : "Sign In"}
                  </Button>
                </StaggerItem>
              </form>
            </StaggerChildren>

            <div className="mt-6 text-center">
              <p className="text-sm text-zinc-500">
                Need help?{" "}
                <a
                  href="mailto:support@adflux.store"
                  className="text-blue-400 hover:underline"
                >
                  Contact Support
                </a>
              </p>
            </div>
          </div>
        </FadeIn>
      </div>
    </div>
  );
}
