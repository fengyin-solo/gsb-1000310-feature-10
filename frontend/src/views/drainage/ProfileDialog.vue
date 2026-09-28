<template>
  <div class="dialog-mask" @click.self="emit('close')">
    <div class="dialog-panel" role="dialog" aria-modal="true" aria-label="淤积变化剖面">
      <header class="dialog-head">
        <div>
          <h3>淤积变化剖面 · {{ entry?.清疏编号 }}</h3>
          <p class="dialog-sub">{{ entry?.清疏管段 }} ｜ 计划 {{ entry?.计划日期 ?? '—' }} ｜ 班组 {{ entry?.清疏班组 ?? '—' }}</p>
        </div>
        <button class="btn ghost" type="button" @click="emit('close')">关闭</button>
      </header>

      <div v-if="errorMessage" class="dialog-error">{{ errorMessage }}</div>

      <template v-if="entry">
        <!-- 统一结论横幅：趋势图、列表、验收结论都取自这一份 profile -->
        <div class="conclusion-banner" :class="`banner-${profile.verdict_tone}`">
          <div class="banner-main">
            <strong>{{ profile.verdict }}</strong>
            <span>{{ profile.conclusion }}</span>
          </div>
          <div class="banner-meta">
            <span v-if="entry.验收时间">上次验收：{{ entry.验收时间 }}</span>
            <span v-if="profile.has_incomparable" class="incomparable-flag">存在不可比区间，已在曲线上标出</span>
          </div>
        </div>

        <TrendChart :profile="profile" />

        <!-- 前后两次比较：按清疏编号、清疏管段、淤积程度、清疏方式四维度对比 -->
        <section class="compare-section">
          <h4>前后两次测量比较</h4>
          <table class="compare-table">
            <thead>
              <tr>
                <th>比较维度</th>
                <th>前次（{{ profile.headline.前次?.测量时间 ?? '—' }}）</th>
                <th>后次（{{ profile.headline.后次?.测量时间 ?? '—' }}）</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>清疏编号</td>
                <td>{{ entry.清疏编号 }}</td>
                <td>{{ entry.清疏编号 }}</td>
              </tr>
              <tr>
                <td>清疏管段</td>
                <td>{{ entry.清疏管段 }}</td>
                <td>{{ entry.清疏管段 }}</td>
              </tr>
              <tr>
                <td>淤积程度</td>
                <td>{{ profile.headline.前次?.淤积程度 ?? '—' }}</td>
                <td>{{ profile.headline.后次?.淤积程度 ?? '—' }}</td>
              </tr>
              <tr>
                <td>清疏方式</td>
                <td>{{ profile.headline.前次?.清疏方式 ?? '—' }}</td>
                <td>{{ profile.headline.后次?.清疏方式 ?? entry.清疏方式 ?? '—' }}</td>
              </tr>
              <tr>
                <td>淤积量（数值）</td>
                <td>{{ formatAmount(profile.headline.前次) }}</td>
                <td>{{ formatAmount(profile.headline.后次) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="headline-line" :class="profile.headline.comparable ? '' : 'headline-bad'">
            {{ profile.headline.conclusion }}
          </p>
        </section>

        <!-- 逐区间列出不可比原因，保证曲线标记可追溯 -->
        <section v-if="profile.segments.length" class="segment-section">
          <h4>测量区间明细</h4>
          <ul class="segment-list">
            <li v-for="(segment, index) in profile.segments" :key="index" :class="segment.comparable ? 'seg-ok' : 'seg-bad'">
              <span class="seg-range">{{ segment.from_time }} → {{ segment.to_time }}</span>
              <span class="seg-status">
                <template v-if="segment.comparable">
                  可比 · {{ segment.trend }}（Δ {{ formatDelta(segment.delta) }}，间隔 {{ segment.gap_days }} 天）
                </template>
                <template v-else>
                  不可比：{{ segment.reasons.join('、') }}
                  <em v-if="segment.gap_days != null && segment.reasons.includes('连续测量断档')">
                    （间隔 {{ segment.gap_days }} 天 &gt; {{ profile.max_gap_days }} 天）
                  </em>
                </template>
              </span>
            </li>
          </ul>
        </section>

        <!-- 验收结果：直接展示 profile 的验收结论；复查动作复用同一份计算 -->
        <section class="accept-section">
          <h4>验收结果</h4>
          <p class="accept-line" :class="`banner-${profile.verdict_tone}`">
            <strong>{{ profile.verdict }}</strong>
            <span>{{ profile.conclusion }}</span>
          </p>
          <div class="accept-actions">
            <button class="btn primary" type="button" :disabled="busy" @click="recheck">
              {{ busy ? '提交中…' : '复查验收' }}
            </button>
            <span class="accept-hint">复查验收依据上述淤积剖面结论，不会另行计算结果。</span>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import TrendChart from './TrendChart.vue'
import type { DrainageEntry, MeasurePoint, Profile } from './types'

const props = defineProps<{ entryId: number }>()
const emit = defineEmits<{
  (event: 'close'): void
  (event: 'accepted', message: string): void
}>()

const entry = ref<DrainageEntry | null>(null)
const errorMessage = ref('')
const busy = ref(false)

const profile = computed<Profile>(() => entry.value!['淤积变化剖面'] as Profile)

function formatAmount(point: MeasurePoint | null): string {
  if (!point) return '—'
  if (point.淤积值 == null || !point.单位) return '缺历史值'
  return `${point.淤积值} ${point.单位}`
}

function formatDelta(delta: number | null): string {
  if (delta == null) return '—'
  return delta > 0 ? `+${delta}` : `${delta}`
}

async function load() {
  errorMessage.value = ''
  try {
    const response = await request(`/api/drainage/${props.entryId}/profile`)
    if (!response.ok) {
      throw new Error('淤积变化剖面读取失败')
    }
    entry.value = (await response.json()) as DrainageEntry
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '淤积变化剖面读取失败'
  }
}

async function recheck() {
  busy.value = true
  errorMessage.value = ''
  try {
    const response = await request(`/api/drainage/${props.entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action: '复查验收' }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || payload?.ok === false) {
      throw new Error(payload?.message ?? '复查验收未生效，请稍后重试')
    }
    emit('accepted', payload?.message ?? '复查验收完成')
    await load()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '复查验收失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 32px 16px;
  z-index: 100;
  overflow-y: auto;
}
.dialog-panel {
  width: min(820px, 100%);
  background: #fff;
  border-radius: 10px;
  border: 1px solid var(--border);
  padding: 18px 20px 22px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.25);
}
.dialog-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.dialog-head h3 { margin: 0; font-size: 17px; }
.dialog-sub { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
.dialog-error { margin: 12px 0; padding: 8px 12px; background: #fdecec; color: #b42318; border-radius: 6px; font-size: 13px; }
.conclusion-banner {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin: 14px 0;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-size: 13px;
}
.conclusion-banner strong { display: block; font-size: 15px; margin-bottom: 2px; }
.banner-main { display: flex; flex-direction: column; gap: 2px; }
.banner-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; font-size: 12px; color: var(--muted); }
.incomparable-flag { color: #b45309; }
.banner-pass { background: #e7f6ec; border-color: #b6e2c3; color: #1a7f37; }
.banner-fail { background: #fdecec; border-color: #f3c2c2; color: #b42318; }
.banner-hold { background: #fef6d9; border-color: #f0dc95; color: #92600a; }
.banner-idle { background: #eef2f7; border-color: #d8dee6; color: #475569; }
.compare-section, .segment-section, .accept-section { margin-top: 18px; }
.compare-section h4, .segment-section h4, .accept-section h4 { margin: 0 0 8px; font-size: 14px; }
.compare-table { width: 100%; border-collapse: collapse; }
.compare-table th, .compare-table td { border: 1px solid var(--border); padding: 7px 10px; font-size: 13px; text-align: left; }
.compare-table th { background: #f8fafc; color: var(--muted); font-weight: 600; }
.headline-line { margin: 8px 0 0; font-size: 13px; color: #1f6feb; }
.headline-bad { color: #b45309; }
.segment-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.segment-list li { display: flex; gap: 10px; align-items: baseline; padding: 7px 10px; border-radius: 6px; font-size: 13px; }
.segment-list li.seg-ok { background: #f4f9ff; border: 1px solid #d3e4fb; }
.segment-list li.seg-bad { background: #fdf6ec; border: 1px solid #f0dc95; }
.seg-range { color: var(--muted); font-size: 12px; white-space: nowrap; }
.seg-status em { font-style: normal; color: var(--muted); }
.accept-line { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border-radius: 8px; border: 1px solid transparent; font-size: 13px; }
.accept-line strong { font-size: 14px; }
.accept-actions { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.accept-hint { color: var(--muted); font-size: 12px; }
</style>
