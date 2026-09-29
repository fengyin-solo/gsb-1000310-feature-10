<template>
  <section class="page" data-module="drainage">
    <header class="page-head">
      <div>
        <h2>排水清疏管理</h2>
        <p class="page-desc">按清疏编号、清疏管段、淤积程度和清疏方式比较前后两次淤积剖面，统一生成趋势与验收结论。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记清疏任务</button>
        <button class="btn" type="button" @click="exportRows">导出排水清疏清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>淤积变化</th>
          <th>验收结果</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in baseColumns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span :class="['trend-badge', trendClass(getProfile(row)?.统计?.趋势)]">
              {{ getProfile(row)?.统计?.趋势 ?? '无法判定' }}
            </span>
          </td>
          <td>
            <span :class="['result-badge', resultClass(getProfile(row)?.结论?.结果)]">
              {{ getProfile(row)?.结论?.结果 ?? '无法验收' }}
            </span>
            <div v-if="getProfile(row)?.结论?.不可比区间数" class="cell-note">
              {{ getProfile(row)?.结论?.不可比区间数 }} 段不可比
            </div>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openProfile(row)">查看剖面</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无排水清疏数据，可先登记清疏任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条排水清疏记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="selectedProfile" class="modal-mask" @click.self="closeProfile">
      <section class="profile-modal" role="dialog" aria-modal="true" aria-label="淤积变化剖面">
        <header class="modal-head">
          <div>
            <h3>淤积变化剖面</h3>
            <p>{{ selectedRow?.['清疏编号'] }} · {{ selectedRow?.['清疏管段'] }}</p>
          </div>
          <button class="modal-close" type="button" aria-label="关闭" @click="closeProfile">×</button>
        </header>

        <div class="profile-meta">
          <div>
            <span>淤积程度</span>
            <strong>{{ selectedProfile['淤积程度'] || '—' }}</strong>
          </div>
          <div>
            <span>清疏方式</span>
            <strong>{{ selectedProfile['清疏方式'] || '—' }}</strong>
          </div>
          <div>
            <span>连续测量间距</span>
            <strong>≤ {{ selectedProfile['连续测量最大间距_m'] }}m</strong>
          </div>
          <div>
            <span>制图单位</span>
            <strong>{{ selectedProfile['制图单位'] }}</strong>
          </div>
        </div>

        <div :class="['conclusion-banner', resultClass(selectedProfile['结论']?.['结果'])]">
          <div>
            <span class="conclusion-result">{{ selectedProfile['结论']?.['结果'] }}</span>
            <span :class="['trend-badge', trendClass(selectedProfile['统计']?.['趋势'])]">
              {{ selectedProfile['统计']?.['趋势'] }}
            </span>
          </div>
          <p>{{ selectedProfile['结论']?.['说明'] }}</p>
        </div>

        <div class="chart-card">
          <div class="chart-title">
            <strong>前后两次淤积深度曲线</strong>
            <span>橙色底色和虚线表示不可比区间，不纳入趋势与验收计算</span>
          </div>
          <svg class="profile-chart" viewBox="0 0 760 320" role="img" aria-label="淤积变化剖面图">
            <line
              v-for="tick in yTicks"
              :key="`grid-${tick.value}`"
              :x1="chart.left"
              :x2="chart.width + chart.left"
              :y1="yPosition(tick.value)"
              :y2="yPosition(tick.value)"
              class="chart-grid"
            />
            <template v-for="segment in selectedProfile['区间']" :key="`gap-${segment['起点里程']}-${segment['终点里程']}`">
              <rect
                v-if="!segment['可比较']"
                :x="xPosition(segment['起点里程'])"
                :y="chart.top"
                :width="Math.max(xPosition(segment['终点里程']) - xPosition(segment['起点里程']), 1)"
                :height="chart.height"
                class="incomparable-band"
              />
            </template>
            <line
              :x1="chart.left"
              :x2="chart.left"
              :y1="chart.top"
              :y2="chart.top + chart.height"
              class="chart-axis"
            />
            <line
              :x1="chart.left"
              :x2="chart.left + chart.width"
              :y1="chart.top + chart.height"
              :y2="chart.top + chart.height"
              class="chart-axis"
            />

            <template v-for="phase in chartPhases" :key="phase.key">
              <path
                v-for="segment in chartSegments(phase.key)"
                :key="`${phase.key}-${segment.start}-${segment.end}`"
                :d="segment.path"
                :class="['profile-line', phase.className, { incomparable: !segment.comparable }]"
              />
              <circle
                v-for="point in chartPoints(phase.key)"
                :key="`${phase.key}-${point['里程']}`"
                :cx="xPosition(point['里程'])"
                :cy="yPosition(Number(point[phase.valueKey]))"
                :r="5"
                :class="[phase.className, { incomparable: !point['纳入趋势'], isolated: !hasSegments }]"
              >
                <title>
                  {{ phase.label }}：{{ point['里程'] }}m，{{ point[phase.displayKey] }}{{ point[phase.unitKey] }}
                  <template v-if="!point['纳入趋势']">（不纳入趋势）</template>
                </title>
              </circle>
            </template>

            <text
              v-for="tick in yTicks"
              :key="`y-${tick.value}`"
              :x="chart.left - 8"
              :y="yPosition(tick.value) + 4"
              text-anchor="end"
              class="chart-label"
            >
              {{ tick.label }}
            </text>
            <text
              v-for="point in selectedProfile['测点']"
              :key="`x-${point['里程']}`"
              :x="xPosition(point['里程'])"
              :y="chart.top + chart.height + 20"
              text-anchor="middle"
              class="chart-label"
            >
              {{ point['里程'] }}m
            </text>
            <text :x="chart.left + chart.width / 2" :y="chart.top + chart.height + 38" text-anchor="middle" class="chart-axis-label">
              管段里程（m）
            </text>
            <text :x="14" :y="chart.top + chart.height / 2" transform="-90 14 160" class="chart-axis-label">
              淤积深度（mm）
            </text>
          </svg>
          <div class="chart-legend">
            <span><i class="legend-dot before"></i>清疏前</span>
            <span><i class="legend-dot after"></i>清疏后</span>
            <span><i class="legend-gap"></i>不可比区间</span>
          </div>
        </div>

        <div class="detail-grid">
          <div class="detail-panel">
            <h4>测点对比</h4>
            <table class="detail-table">
              <thead>
                <tr>
                  <th>里程</th>
                  <th>清疏前</th>
                  <th>清疏后</th>
                  <th>变化</th>
                  <th>可比性</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="point in selectedProfile['测点']" :key="point['里程']">
                  <td>{{ point['里程'] }}m</td>
                  <td>{{ formatMeasure(point['清疏前显示值'], point['清疏前单位']) }}</td>
                  <td>{{ formatMeasure(point['清疏后显示值'], point['清疏后单位']) }}</td>
                  <td>{{ formatPointDelta(point) }}</td>
                  <td>
                    <span :class="point['纳入趋势'] ? 'ok-text' : 'warning-text'">
                      {{ point['纳入趋势'] ? '纳入趋势' : (point['测点可比较'] ? '不纳入趋势' : '不可比') }}
                    </span>
                    <div v-if="point['不可比原因']?.length" class="cell-note">
                      {{ point['不可比原因'].join('、') }}
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="detail-panel">
            <h4>区间判定</h4>
            <ul class="segment-list">
              <li v-for="segment in selectedProfile['区间']" :key="`${segment['起点里程']}-${segment['终点里程']}`">
                <div>
                  <strong>{{ segment['起点里程'] }}m — {{ segment['终点里程'] }}m</strong>
                  <span>{{ segment['长度_m'] }}m</span>
                </div>
                <span :class="segment['可比较'] ? 'ok-text' : 'warning-text'">
                  {{ segment['可比较'] ? '可比较' : segment['不可比原因'].join('、') }}
                </span>
              </li>
              <li v-if="!selectedProfile['区间'].length" class="empty-inline">不足两个测点，暂不能形成连续剖面区间</li>
            </ul>

            <dl class="stats-list">
              <div>
                <dt>平均清疏前</dt>
                <dd>{{ formatMm(selectedProfile['统计']?.['平均清疏前_mm']) }}</dd>
              </div>
              <div>
                <dt>平均清疏后</dt>
                <dd>{{ formatMm(selectedProfile['统计']?.['平均清疏后_mm']) }}</dd>
              </div>
              <div>
                <dt>平均下降率</dt>
                <dd>{{ formatRate(selectedProfile['统计']?.['下降率']) }}</dd>
              </div>
              <div>
                <dt>不可比区间</dt>
                <dd>{{ selectedProfile['统计']?.['不可比区间数'] }} 段</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type JsonRecord = Record<string, unknown>
type MaybeNumber = number | null

interface ProfilePoint extends JsonRecord {
  里程: number
  清疏前: MaybeNumber
  清疏前显示值: MaybeNumber
  清疏前单位: string | null
  清疏后: MaybeNumber
  清疏后显示值: MaybeNumber
  清疏后单位: string | null
  测点可比较: boolean
  不可比原因: string[]
  纳入趋势: boolean
}

interface ProfileSegment extends JsonRecord {
  起点里程: number
  终点里程: number
  长度_m: number
  可比较: boolean
  不可比原因: string[]
}

interface ProfileStatistics extends JsonRecord {
  可比较区间数: number
  不可比区间数: number
  可比较长度_m: number
  纳入趋势测点数: number
  平均清疏前_mm: MaybeNumber
  平均清疏后_mm: MaybeNumber
  平均变化_mm: MaybeNumber
  下降率: MaybeNumber
  趋势: string
}

interface ProfileConclusion extends JsonRecord {
  结果: string
  趋势: string
  说明: string
  不可比区间数: number
  不可比区间: Array<Record<string, unknown>>
}

interface Profile extends JsonRecord {
  清疏编号: string
  清疏管段: string
  淤积程度: string
  清疏方式: string
  制图单位: string
  连续测量最大间距_m: number
  测点: ProfilePoint[]
  区间: ProfileSegment[]
  统计: ProfileStatistics
  结论: ProfileConclusion
}

interface Row extends JsonRecord {
  id: number
  淤积变化剖面?: Profile
  [key: string]: unknown
}

interface ActionResponse {
  ok: boolean
  message: string
  entry?: Row
}

const ENDPOINT = '/api/drainage'
const baseColumns = ['清疏编号', '清疏管段', '淤积程度', '清疏方式', '计划日期', '清疏班组', '清出淤泥量', '清疏状态']
const columns = [...baseColumns]
const actions = ['安排清疏', '开始清疏', '复查验收']
const filterFields = baseColumns.slice(0, 4)

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const selectedRow = ref<Row | null>(null)
const profileDetail = ref<Profile | null>(null)

const stats = computed(() => [
  { label: '待清疏管段', value: rows.value.filter((row) => row.status === '待清疏').length },
  { label: '需复查管段', value: rows.value.filter((row) => row.status === '需复查').length },
  { label: '已完成清疏', value: rows.value.filter((row) => row.status === '已清疏').length },
])

const selectedProfile = computed<Profile | null>(() => profileDetail.value ?? selectedRow.value?.淤积变化剖面 ?? null)
const hasSegments = computed(() => Boolean(selectedProfile.value?.区间.some((segment) => segment.可比较)))

const chart = { left: 58, top: 24, width: 660, height: 220 }
const chartPhases = [
  { key: 'before', label: '清疏前', valueKey: '清疏前', displayKey: '清疏前显示值', unitKey: '清疏前单位', className: 'before' },
  { key: 'after', label: '清疏后', valueKey: '清疏后', displayKey: '清疏后显示值', unitKey: '清疏后单位', className: 'after' },
] as const

const xDomain = computed(() => {
  const positions = selectedProfile.value?.测点.map((point) => point.里程) ?? []
  const min = Math.min(0, ...positions)
  const max = Math.max(1, ...positions)
  return { min, max: max === min ? min + 1 : max }
})

const yDomain = computed(() => {
  const values = (selectedProfile.value?.测点 ?? [])
    .flatMap((point) => [point.清疏前, point.清疏后])
    .filter((value): value is number => typeof value === 'number')
  return Math.max(10, ...values.map((value) => value * 1.1))
})

const yTicks = computed(() => {
  const max = yDomain.value
  return [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    value: Number((max * ratio).toFixed(1)),
    label: Math.round(max * ratio).toString(),
  }))
})

function getProfile(row: Row): Profile | undefined {
  return row.淤积变化剖面
}

function xPosition(value: number): number {
  const { min, max } = xDomain.value
  return chart.left + ((value - min) / (max - min)) * chart.width
}

function yPosition(value: number): number {
  return chart.top + chart.height - (value / yDomain.value) * chart.height
}

function chartPoints(phase: 'before' | 'after'): ProfilePoint[] {
  const key = phase === 'before' ? '清疏前' : '清疏后'
  return (selectedProfile.value?.测点 ?? []).filter((point) => typeof point[key] === 'number')
}

function chartSegments(phase: 'before' | 'after') {
  const key = phase === 'before' ? '清疏前' : '清疏后'
  const pointMap = new Map((selectedProfile.value?.测点 ?? []).map((point) => [point.里程, point]))
  return (selectedProfile.value?.区间 ?? [])
    .map((segment) => {
      const startPoint = pointMap.get(segment.起点里程)
      const endPoint = pointMap.get(segment.终点里程)
      const start = startPoint?.[key]
      const end = endPoint?.[key]
      if (typeof start !== 'number' || typeof end !== 'number' || !startPoint || !endPoint) {
        return null
      }
      return {
        start: segment.起点里程,
        end: segment.终点里程,
        comparable: segment.可比较,
        path: `M ${xPosition(segment.起点里程)} ${yPosition(start)} L ${xPosition(segment.终点里程)} ${yPosition(end)}`,
      }
    })
    .filter((item): item is NonNullable<typeof item> => item !== null)
}

function formatMeasure(value: MaybeNumber, unit: string | null): string {
  if (value === null || value === undefined) return '缺测'
  return `${value}${unit ? ` ${unit}` : ''}`
}

function formatMm(value: MaybeNumber): string {
  return typeof value === 'number' ? `${value} mm` : '—'
}

function formatRate(value: MaybeNumber): string {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—'
}

function formatPointDelta(point: ProfilePoint): string {
  if (point.清疏前 === null || point.清疏后 === null || !point.测点可比较) return '—'
  const delta = Number((point.清疏后 - point.清疏前).toFixed(1))
  const prefix = delta > 0 ? '+' : ''
  return `${prefix}${delta} mm`
}

function trendClass(trend?: string): string {
  if (trend === '淤积改善') return 'trend-improved'
  if (trend === '淤积反弹') return 'trend-rebound'
  if (trend === '无明显变化') return 'trend-flat'
  return 'trend-unknown'
}

function resultClass(result?: string): string {
  if (result === '验收通过') return 'result-pass'
  if (result === '验收不通过') return 'result-fail'
  return 'result-warning'
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '清疏任务登记入口尚未接入审批流'
}

async function openProfile(row: Row) {
  errorMessage.value = ''
  selectedRow.value = row
  profileDetail.value = null
  try {
    const response = await request(`${ENDPOINT}/${row.id}/profile`)
    if (!response.ok) {
      throw new Error('淤积变化剖面读取失败')
    }
    profileDetail.value = (await response.json()) as Profile
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '淤积剖面读取失败'
  }
}

function closeProfile() {
  selectedRow.value = null
  profileDetail.value = null
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('排水清疏动作未生效，请稍后重试')
    }
    const payload = (await response.json()) as ActionResponse
    if (!payload.ok) {
      errorMessage.value = payload.message
    }
    await reload()
    if (selectedRow.value?.id === row.id && payload.entry?.淤积变化剖面) {
      selectedRow.value = payload.entry
      profileDetail.value = payload.entry.淤积变化剖面
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水清疏操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const activeFilters = Object.fromEntries(
    Object.entries(filters.value).filter(([, value]) => value.trim()),
  )
  const query = new URLSearchParams(activeFilters).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('清疏任务列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水清疏列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.trend-badge,
.result-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.trend-improved { background: #dcfce7; color: #166534; }
.trend-rebound { background: #fee2e2; color: #991b1b; }
.trend-flat { background: #e0f2fe; color: #075985; }
.trend-unknown { background: #f1f5f9; color: #475569; }

.result-pass { background: #dcfce7; color: #166534; }
.result-fail { background: #fee2e2; color: #991b1b; }
.result-warning { background: #fef3c7; color: #92400e; }

.cell-note {
  margin-top: 3px;
  color: #92400e;
  font-size: 11px;
  line-height: 1.4;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.55);
}

.profile-modal {
  width: min(920px, 96vw);
  max-height: 92vh;
  overflow: auto;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.28);
}

.modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
}

.modal-head h3 { margin: 0; }
.modal-head p { margin: 4px 0 0; color: var(--muted); font-size: 13px; }
.modal-close { border: none; background: none; font-size: 28px; line-height: 1; cursor: pointer; color: var(--muted); }

.profile-meta {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 16px 22px 0;
}

.profile-meta div {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px;
  background: #f8fafc;
}

.profile-meta span,
.chart-title span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.profile-meta strong { display: block; margin-top: 4px; font-size: 14px; }

.conclusion-banner {
  margin: 14px 22px;
  border: 1px solid;
  border-radius: 10px;
  padding: 12px 14px;
}

.conclusion-banner.result-pass { background: #f0fdf4; border-color: #86efac; }
.conclusion-banner.result-fail { background: #fef2f2; border-color: #fca5a5; }
.conclusion-banner.result-warning { background: #fffbeb; border-color: #fcd34d; }
.conclusion-banner p { margin: 6px 0 0; font-size: 13px; }
.conclusion-result { margin-right: 8px; font-weight: 700; }

.chart-card {
  margin: 0 22px;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}

.chart-title { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px; }
.profile-chart { width: 100%; height: auto; }
.chart-grid { stroke: #e5e7eb; stroke-width: 1; }
.chart-axis { stroke: #64748b; stroke-width: 1.2; }
.chart-label { fill: #475569; font-size: 11px; }
.chart-axis-label { fill: #64748b; font-size: 12px; }
.incomparable-band { fill: #f59e0b; opacity: 0.16; }
.profile-line { fill: none; stroke-width: 2.6; }
.profile-line.before, .circle.before { stroke: #2563eb; }
.profile-line.after, .circle.after { stroke: #16a34a; }
.circle { fill: #fff; stroke-width: 2.5; }
.circle.incomparable { fill: #fff7ed; stroke: #f97316; }
.profile-line.incomparable { stroke: #f97316; stroke-dasharray: 6 5; }

.chart-legend {
  display: flex;
  gap: 18px;
  color: var(--muted);
  font-size: 12px;
}

.legend-dot,
.legend-gap { display: inline-block; vertical-align: middle; margin-right: 5px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.legend-dot.before { background: #2563eb; }
.legend-dot.after { background: #16a34a; }
.legend-gap { width: 20px; height: 8px; background: rgba(245, 158, 11, 0.24); border: 1px dashed #f97316; }

.detail-grid {
  display: grid;
  grid-template-columns: 1.25fr 0.75fr;
  gap: 14px;
  padding: 16px 22px 22px;
}

.detail-panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}

.detail-panel h4 { margin: 0; padding: 11px 12px; border-bottom: 1px solid var(--border); background: #f8fafc; }
.detail-table { border: 0; }
.detail-table th, .detail-table td { font-size: 12px; padding: 7px 8px; }

.segment-list { list-style: none; margin: 0; padding: 8px 12px; }
.segment-list li { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 0; border-bottom: 1px dashed #e5e7eb; font-size: 12px; }
.segment-list li:last-child { border-bottom: 0; }
.segment-list strong { display: block; }
.segment-list span { color: var(--muted); }
.empty-inline { color: var(--muted); }

.stats-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 0; padding: 10px 12px 14px; }
.stats-list div { border-radius: 8px; background: #f8fafc; padding: 8px; }
.stats-list dt { color: var(--muted); font-size: 11px; }
.stats-list dd { margin: 3px 0 0; font-weight: 700; font-size: 14px; }
.ok-text { color: #166534; }
.warning-text { color: #92400e; }

@media (max-width: 860px) {
  .profile-meta,
  .detail-grid { grid-template-columns: 1fr; }
  .chart-title { align-items: flex-start; flex-direction: column; }
}
</style>
