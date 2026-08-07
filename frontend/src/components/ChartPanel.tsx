/** ECharts wrapper for Smart Query results */

import type { CSSProperties } from 'react'
import ReactECharts from 'echarts-for-react'
import { Card } from 'antd'

interface Props {
  type: string
  config: {
    x?: string
    y?: string
    title?: string
    columns?: string[]
    data?: any[][]
  }
  data?: { columns: string[]; rows: any[][] }
  style?: CSSProperties
}

const CHART_TYPE_MAP: Record<string, string> = {
  bar: 'bar',
  bar_horizontal: 'bar',
  line: 'line',
  pie: 'pie',
  area: 'line',
  number: 'none',
  table: 'none',
  none: 'none',
}

export default function ChartPanel({ type, config, data, style }: Props) {
  if (!data?.rows?.length || type === 'none' || type === 'table') return null

  const cols = data.columns
  const rows = data.rows

  // Extract axis data
  const xField = config.x || cols[0]
  const yField = config.y || (cols.length > 1 ? cols[1] : cols[0])
  const xIdx = cols.indexOf(xField)
  const yIdx = cols.indexOf(yField)

  const xData = rows.map((r) => r[xIdx])
  const yData = rows.map((r) => Number(r[yIdx]) || 0)

  const isHorizontal = type === 'bar_horizontal'

  const option: any = {
    title: { text: config.title || '', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'axis' as const },
    grid: { containLabel: true, left: 60, right: 30, top: 40, bottom: 30 },
    xAxis: isHorizontal
      ? { type: 'value' as const }
      : { type: 'category' as const, data: xData, axisLabel: { rotate: xData.length > 8 ? 30 : 0 } },
    yAxis: isHorizontal
      ? { type: 'category' as const, data: xData }
      : { type: 'value' as const },
    series: [
      {
        name: yField,
        type: CHART_TYPE_MAP[type] || 'bar',
        data: isHorizontal ? yData : yData,
        smooth: type === 'area' || type === 'line',
        areaStyle: type === 'area' ? { opacity: 0.15 } : undefined,
        itemStyle: { borderRadius: type.includes('bar') ? [4, 4, 0, 0] : 0 },
      },
    ],
  }

  if (type === 'pie') {
    option.series = [{
      type: 'pie',
      radius: ['35%', '65%'],
      data: rows.map((r, i) => ({ name: String(r[xIdx]), value: Number(r[yIdx]) || 0 })),
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)' } },
      label: { formatter: '{b}: {c} ({d}%)' },
    }]
    delete option.xAxis
    delete option.yAxis
  }

  return (
    <Card size="small" title={config.title || '数据图表'} style={{ marginTop: 12, ...style }}>
      <ReactECharts option={option} style={{ height: Math.min(350, rows.length * 32 + 60) }} notMerge opts={{ renderer: 'canvas' }} />
    </Card>
  )
}
