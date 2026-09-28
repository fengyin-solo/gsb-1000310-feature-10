/** 淤积变化剖面接口结构，与后端 app/profile.py 的 build_profile 输出对齐。 */

export interface MeasurePoint {
  seq: number
  测量时间: string | null
  淤积程度: string | null
  淤积值: number | null
  单位: string | null
  淤积显示: string
  清疏方式: string | null
  comparable: boolean
  missing: boolean
}

export interface CompareSegment {
  from_seq: number
  to_seq: number
  from_time: string | null
  to_time: string | null
  comparable: boolean
  reasons: string[]
  gap_days: number | null
  前次: MeasurePoint
  后次: MeasurePoint
  前值: number | null
  后值: number | null
  前单位: string | null
  后单位: string | null
  trend: string | null
  delta: number | null
}

export interface Headline {
  comparable: boolean
  reasons: string[]
  trend: string | null
  delta: number | null
  gap_days: number | null
  前次: MeasurePoint | null
  后次: MeasurePoint | null
  conclusion: string
}

export interface Profile {
  points: MeasurePoint[]
  segments: CompareSegment[]
  headline: Headline
  verdict: string
  verdict_tone: 'pass' | 'fail' | 'hold' | 'idle' | string
  conclusion: string
  summary_key: string
  summary_text: string
  max_gap_days: number
  has_incomparable: boolean
}

export interface DrainageEntry {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  清疏编号: string
  清疏管段: string
  淤积程度: string
  清疏方式: string
  计划日期?: string
  清疏班组?: string
  清出淤泥量?: string
  清疏状态?: string
  验收结论?: string
  验收说明?: string
  验收时间?: string
  '淤积变化剖面': Profile
  [key: string]: unknown
}
