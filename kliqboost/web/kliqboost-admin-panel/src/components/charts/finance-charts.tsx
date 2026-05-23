"use client"

/**
 * Finance page charts (revenue bar + commission donut), extracted so
 * recharts (~150 KB gzipped) only loads on the /finance route after
 * the rest of the page has rendered.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatCurrency } from "@/lib/utils"

interface BarDatum {
  name: string
  amount: number
}

interface PieDatum {
  name: string
  value: number
}

const TOOLTIP_STYLE = {
  backgroundColor: "#0f172a",
  border: "1px solid #334155",
  borderRadius: "8px",
  color: "#f8fafc",
} as const

export function RevenueBarChart({ data }: { data: BarDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => formatCurrency(Number(value))}
        />
        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function CommissionPieChart({
  data,
  colors,
}: {
  data: PieDatum[]
  colors: readonly string[]
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={4}
          dataKey="value"
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
          ))}
        </Pie>
        <Tooltip contentStyle={TOOLTIP_STYLE} />
      </PieChart>
    </ResponsiveContainer>
  )
}
