<template>
  <div class="trend-chart">
    <svg v-if="layout" :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="`淤积变化趋势图，共 ${profile.points.length} 次测量`">
      <!-- 纵向网格 + 刻度 -->
      <g>
        <line
          v-for="tick in layout.ticks"
          :key="`grid-${tick.value}`"
          :x1="PAD_L"
          :x2="W - PAD_R"
          :y1="tick.y"
          :y2="tick.y"
          class="grid-line"
        />
        <text
          v-for="tick in layout.ticks"
          :key="`tick-${tick.value}`"
          :x="PAD_L - 6"
          :y="tick.y + 4"
          text-anchor="end"
          class="axis-text"
        >{{ tick.value }}</text>
      </g>

      <!-- 区间连线：可比实线，不可比虚线 -->
      <g>
        <line
          v-for="(segment, index) in layout.links"
          :key="`seg-${index}`"
          :x1="segment.x1"
          :y1="segment.y1"
          :x2="segment.x2"
          :y2="segment.y2"
          :class="['seg-line', segment.comparable ? 'seg-ok' : 'seg-bad']"
        />
        <text
          v-for="(segment, index) in layout.links"
          v-show="!segment.comparable"
          :key="`seg-label-${index}`"
          :x="(segment.x1 + segment.x2) / 2"
          :y1="(segment.y1 + segment.y2) / 2"
          :y="(segment.y1 + segment.y2) / 2 - 6"
          text-anchor="middle"
          class="seg-label"
        >不可比 · {{ segment.reason }}</text>
      </g>

      <!-- 测量点：有值实心，缺值空心警示 -->
      <g>
        <template v-for="(point, index) in layout.points" :key="`point-${index}`">
          <circle
            :cx="point.x"
            :cy="point.missing ? H - PAD_B : point.y"
            :r="5"
            :class="['point-dot', point.missing ? 'point-missing' : 'point-valid']"
          >
            <title>{{ point.time }} · {{ point.label }}{{ point.missing ? '（缺历史值）' : '' }}</title>
          </circle>
          <text :x="point.x" :y="H - PAD_B + 18" text-anchor="middle" class="axis-text">{{ point.shortTime }}</text>
        </template>
      </g>
    </svg>
    <p v-if="!layout" class="chart-empty">该任务暂无淤积测量记录，先补测后再比较前后淤积变化。</p>
    <div class="chart-legend">
      <span><i class="legend-line ok"></i>可比区间</span>
      <span><i class="legend-line bad"></i>不可比区间</span>
      <span v-if="layout">纵轴单位：{{ layout.unit || '—' }}（不跨单位连线比较）</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { CompareSegment, Profile } from './types'

const props = defineProps<{ profile: Profile }>()

const W = 720
const H = 280
const PAD_L = 48
const PAD_R = 20
const PAD_T = 28
const PAD_B = 40

interface PlottedPoint {
  x: number
  y: number
  missing: boolean
  label: string
  time: string
  shortTime: string
  unit: string | null
}
interface PlottedLink {
  x1: number
  y1: number
  x2: number
  y2: number
  comparable: boolean
  reason: string
}
interface Layout {
  points: PlottedPoint[]
  links: PlottedLink[]
  ticks: { value: number; y: number }[]
  unit: string | null
}

const layout = computed<Layout | null>(() => {
  const points = props.profile.points
  if (!points.length) return null

  const innerW = W - PAD_L - PAD_R
  const innerH = H - PAD_T - PAD_B
  // x 轴按测量次序等距分布（缺时间的点也保留位置，缺口由断档区间表达）
  const stepX = points.length > 1 ? innerW / (points.length - 1) : 0
  const xAt = (index: number) => PAD_L + (points.length > 1 ? stepX * index : innerW / 2)

  const unit = points.find(point => point.单位)?.单位 ?? null
  const values = points.map(point => point.淤积值).filter((value): value is number => value != null)
  const maxValue = values.length ? Math.max(...values) : 1
  // 顶端留 15% 余量，避免数值标签贴边
  const yMax = Math.max(maxValue * 1.15, 1)
  const yAt = (value: number) => PAD_T + innerH - (value / yMax) * innerH

  const tickCount = 4
  const ticks = Array.from({ length: tickCount + 1 }, (_, index) => {
    const value = (yMax / tickCount) * index
    return { value: Math.round(value * 10) / 10, y: yAt(value) }
  })

  const plotted: PlottedPoint[] = points.map((point, index) => ({
    x: xAt(index),
    y: point.淤积值 == null ? H - PAD_B : yAt(point.淤积值),
    missing: point.missing || point.淤积值 == null,
    label: point.淤积显示,
    time: point.测量时间 ?? '时间缺失',
    shortTime: (point.测量时间 ?? '缺时间').slice(5),
    unit: point.单位,
  }))

  const links: PlottedLink[] = props.profile.segments.map((segment: CompareSegment, index) => {
    const from = plotted[index]
    const to = plotted[index + 1]
    return {
      x1: from.x,
      y1: from.y,
      x2: to.x,
      y2: to.y,
      comparable: segment.comparable,
      reason: segment.reasons[0] ?? '不可比',
    }
  })

  return { points: plotted, links, ticks, unit }
})
</script>

<style scoped>
.trend-chart { width: 100%; background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.trend-chart svg { width: 100%; height: auto; display: block; }
.grid-line { stroke: #eef2f7; stroke-width: 1; }
.axis-text { fill: var(--muted); font-size: 11px; }
.seg-line { stroke-width: 2; fill: none; }
.seg-ok { stroke: #1f6feb; }
.seg-bad { stroke: #d97706; stroke-dasharray: 6 5; }
.seg-label { fill: #b45309; font-size: 11px; }
.point-valid { fill: #1f6feb; stroke: #fff; stroke-width: 1.5; }
.point-missing { fill: #fff; stroke: #d97706; stroke-width: 2; }
.chart-empty { margin: 0; padding: 40px 0; text-align: center; color: var(--muted); font-size: 13px; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-top: 8px; color: var(--muted); font-size: 12px; }
.legend-line { display: inline-block; width: 22px; height: 0; border-top-width: 3px; border-top-style: solid; margin-right: 6px; vertical-align: middle; }
.legend-line.ok { border-top-color: #1f6feb; }
.legend-line.bad { border-top-color: #d97706; border-top-style: dashed; }
</style>
