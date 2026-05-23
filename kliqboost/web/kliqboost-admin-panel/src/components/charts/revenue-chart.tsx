"use client"

/**
 * Revenue line chart, extracted from dashboard/page.tsx so the heavy
 * recharts bundle is only loaded when this component mounts.
 *
 * The dashboard imports this via next/dynamic({ ssr: false }) which
 * keeps recharts (~150 KB gzipped) out of the initial route chunk.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export interface RevenueChartPoint {
  date: string
  revenue: number
}

export default function RevenueChart({ data }: { data: RevenueChartPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#71717a" }}
          tickFormatter={(v: string) => v.slice(5)}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#71717a" }}
          tickFormatter={(v: number) =>
            `$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`
          }
          tickLine={false}
          axisLine={false}
          width={52}
        />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value) => [`$${Number(value).toFixed(2)}`, "Revenue"]}
        />
        <Line
          type="monotone"
          dataKey="revenue"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#10b981" }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
