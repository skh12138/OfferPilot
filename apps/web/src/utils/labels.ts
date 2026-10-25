const labels: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  succeeded: "已完成",
  partial: "部分完成",
  failed: "失败",
  cancelled: "已取消",
  resume_parse: "简历解析",
  job_import: "岗位导入",
  search: "岗位搜索",
  search_parse: "条件解析",
  search_organize: "招聘信息整理",
  material_prepare: "材料准备",
  study: "题单生成",
  feedback: "回答反馈",
  export: "数据导出",
  delete_resume: "简历清理",
  delete_account: "账户清理",
  interview_sources: "面经检索",
  job_refresh: "来源刷新",
  unassigned: "未设置意向",
  interested: "意向",
  preparing: "准备投递",
  submitted: "已投递",
  assessment: "考核中",
  offer: "Offer 沟通",
  onboarding: "已接受 / 入职",
  closed: "已结束",
  confirmed: "已确认",
  unreviewed: "待校对",
  conflict: "有冲突",
  missing: "缺失",
  pass: "符合已确认条件",
  fail: "存在条件冲突",
  unknown: "待核实",
  user_provided: "用户提供",
  official_verified: "有官方关联证据",
  repost: "转载",
  unverified: "来源未核实",
  page_open: "页面显示开放",
  expired: "明确已过期",
  not_assessed: "风险未评估",
  no_known_flags: "未检出已知风险",
  needs_review: "需要复核",
  high_risk_flag: "高风险线索",
  days_per_week: "每周天数",
  duration_months: "持续月数",
  graduation_year: "毕业届别",
  cities: "城市",
  work_mode: "办公方式",
  education: "学历",
  secondary: "中等教育",
  associate: "大专",
  bachelor: "本科",
  master: "硕士",
  doctor: "博士",
  onsite: "现场办公",
  remote: "远程办公",
  hybrid: "混合办公",
  department: "部门",
  deadline: "截止日期",
  hard: "硬性要求",
  preferred: "优先条件",
  negotiable: "可协商",
  todo: "待办",
  in_progress: "进行中",
  waiting_external: "等待外部",
  done: "已完成",
  pending: "待安排",
  scheduled: "已安排",
  completed_waiting_result: "已完成，待结果",
  passed: "本人记录通过",
  skipped: "已跳过",
  new: "尚未评估",
  practicing: "练习中",
  confident: "本人确认掌握",
  priority: "重点推进",
  paused: "暂缓",
  excluded: "不考虑",
};
export function label(value: string | number): string {
  return labels[String(value)] ?? String(value);
}

export function preferenceLabel(value: string) {
  return (
    (
      {
        priority: "重点推进",
        interested: "一般关注",
        paused: "暂缓",
        excluded: "不考虑",
        unassigned: "未设置",
      } as Record<string, string>
    )[value] ?? label(value)
  );
}

export function difficultyLabel(value: string) {
  return (
    ({ easy: "入门", medium: "适中", hard: "较难" } as Record<string, string>)[
      value
    ] ?? value
  );
}
