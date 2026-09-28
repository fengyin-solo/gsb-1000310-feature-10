<template>
  <section class="page" data-module="drainage">
    <header class="page-head">
      <div>
        <h2>排水清疏管理</h2>
        <p class="page-desc">维护清疏任务，围绕清疏编号、清疏管段、淤积程度、清疏方式做登记、筛选与状态流转，并比较前后两次淤积变化。</p>
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
      <label class="filter-item">
        <span>清疏编号</span>
        <input v-model="keyword" placeholder="按清疏编号检索" />
      </label>
      <label class="filter-item">
        <span>清疏状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table drainage-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>淤积变化结论</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span class="verdict-chip" :class="toneClass(String(row['结论标识'] ?? 'none'))" :title="String(row['结论说明'] ?? '')">
              {{ row['淤积变化结论'] ?? '—' }}
              <em v-if="row['存在不可比区间']" class="incomparable-dot">●</em>
            </span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openProfile(row)">淤积变化剖面</button>
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
          <td :colspan="columns.length + 2" class="empty-state">暂无排水清疏数据，可先登记清疏任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条排水清疏记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
    </footer>

    <ProfileDialog
      v-if="profileTargetId !== null"
      :entry-id="profileTargetId"
      @close="closeProfile"
      @accepted="onAccepted"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import ProfileDialog from './ProfileDialog.vue'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/drainage'
const columns = ["清疏编号", "清疏管段", "淤积程度", "清疏方式", "计划日期", "清疏班组", "清出淤泥量", "清疏状态"]
const actions = ["安排清疏", "开始清疏", "复查验收"]
const statuses = ["待清疏", "清疏中", "已清疏", "需复查"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const profileTargetId = ref<number | null>(null)

const stats = computed(() => [
  { label: '待清疏管段', value: countByStatus('待清疏') },
  { label: '清疏中管段', value: countByStatus('清疏中') },
  { label: '需复查管段', value: countByStatus('需复查') },
])

function countByStatus(target: string): number {
  return rows.value.filter(row => String(row.status ?? '') === target).length
}

function toneClass(tone: string): string {
  return `tone-${tone}`
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '清疏任务登记入口尚未接入审批流'
}

function openProfile(row: Row) {
  errorMessage.value = ''
  profileTargetId.value = Number(row.id)
}

function closeProfile() {
  profileTargetId.value = null
}

function onAccepted(message: string) {
  noticeMessage.value = message
  setTimeout(() => { noticeMessage.value = '' }, 6000)
  void reload()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = await response.json().catch(() => null) as { message?: string } | null
    if (!response.ok) {
      throw new Error(payload?.message ?? '排水清疏动作未生效，请稍后重试')
    }
    noticeMessage.value = payload?.message ?? `清疏任务已${action}`
    setTimeout(() => { noticeMessage.value = '' }, 6000)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水清疏操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('清疏任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水清疏列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.drainage-table .row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.verdict-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 18px;
  background: #eef2f7;
  color: #475569;
  white-space: nowrap;
}
.verdict-chip.tone-down { background: #e7f6ec; color: #1a7f37; }
.verdict-chip.tone-up { background: #fdecec; color: #b42318; }
.verdict-chip.tone-flat { background: #fdf3e2; color: #b5570a; }
.verdict-chip.tone-hold { background: #fef6d9; color: #92600a; }
.verdict-chip.tone-none { background: #eef2f7; color: #64748b; }
.incomparable-dot {
  font-style: normal;
  font-size: 9px;
  color: #d97706;
}
.filter-item select {
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.notice-text { color: #1a7f37; }
</style>
