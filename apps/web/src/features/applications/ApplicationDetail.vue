<script setup lang="ts">
import { ElMessageBox } from "element-plus";
import { ref } from "vue";
import DraftDrawer from "../../components/DraftDrawer.vue";
import { useChoiceQuery } from "../../app/navigation";
import { useUi } from "../../app/ui";
import { formatDate } from "../../utils/dates";
import { label } from "../../utils/labels";
import SubmissionSnapshot from "./SubmissionSnapshot.vue";
import ManualMaterialForm from "../preparation/ManualMaterialForm.vue";
import RunStatus from "../../components/RunStatus.vue";
import BundleCard from "../preparation/BundleCard.vue";
import { useApplicationActions } from "./useApplicationActions";
const {
  id,
  app,
  rounds,
  events,
  submissions,
  bundles,
  profile,
  tasks,
  jobs,
  refresh,
  busy,
  error,
  runId,
  basisJobId,
  dialog,
  profileId,
  missing,
  confirmed,
  submittedAt,
  observed,
  target,
  eventType,
  reason,
  taskAction,
  links,
  linksDirty,
  inputsDirty,
  resetInputs,
  resetLinks,
  round,
  editingRound,
  submit,
  check,
  stage,
  saveRound,
  editRound,
  saveLinks,
  prepare,
  changeBasis,
} = useApplicationActions();
const tab = useChoiceQuery(
    "tab",
    ["overview", "materials", "rounds", "practice", "tasks", "history"],
    "overview",
  ),
  ui = useUi(),
  linkEditor = ref(false);
async function discardInputs() {
  try {
    await ElMessageBox.confirm(
      "放弃此申请尚未提交的表单输入，并重新读取当前状态。",
      "重新填写？",
      {
        confirmButtonText: "放弃输入并重新读取",
        cancelButtonText: "继续编辑",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  await refresh();
  resetInputs();
}
async function discardLinks() {
  try {
    await ElMessageBox.confirm(
      "放弃入口草稿并载入服务器当前链接。",
      "载入最新入口？",
      {
        confirmButtonText: "放弃并载入最新",
        cancelButtonText: "继续编辑",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  await refresh();
  resetLinks();
}
async function saveEntrance() {
  await saveLinks();
  if (!error.value) linkEditor.value = false;
}
</script>
<template>
  <RouterLink :to="ui.lists['/applications'] || '/applications'"
    >← 我的申请</RouterLink
  ><el-alert
    v-if="error && !dialog && !linkEditor"
    type="error"
    :title="error"
  /><el-skeleton v-if="app.isPending.value" animated /><el-alert
    v-if="app.error.value"
    title="申请读取失败"
    type="error"
  /><el-button v-if="app.error.value" @click="app.refetch()"
    >重新加载申请详情</el-button
  ><template v-if="app.data.value"
    ><h1 class="detail-title" style="margin-top: 20px">
      {{ app.data.value.company }} · {{ app.data.value.title }}
    </h1>
    <p class="subtitle">
      <el-tag>{{ label(app.data.value.stage) }}</el-tag> · 公司原始状态：{{
        app.data.value.company_status_raw || "未记录"
      }}
      · 准备基准 {{ app.data.value.basis_revision }}
    </p>
    <div class="toolbar">
      <a
        v-if="app.data.value.progress_url"
        :href="app.data.value.progress_url"
        target="_blank"
        rel="noopener noreferrer"
        >打开进度页面 ↗</a
      ><el-button @click="tab = 'overview'">记录进度</el-button>
      <el-button type="primary" @click="dialog = 'submission'"
        >记录实际投递</el-button
      ><el-button @click="dialog = 'stage'">阶段 / 更正 / 重开</el-button
      ><el-button
        @click="
          editingRound = undefined;
          dialog = 'round';
        "
        >新增考核轮次</el-button
      ><el-button @click="prepare">准备材料草稿</el-button>
    </div>
    <RunStatus v-if="runId" :id="runId" @complete="refresh" />
    <el-tabs v-model="tab"
      ><el-tab-pane label="概览与进度" name="overview" lazy
        ><section class="panel">
          <h2>三个外部入口</h2>
          <div class="toolbar">
            <template
              v-for="[field, name] in [
                ['job_url', '岗位详情'],
                ['apply_url', '投递入口'],
                ['progress_url', '进度入口'],
              ] as const"
              :key="field"
              ><a
                v-if="app.data.value[field]"
                :href="app.data.value[field] ?? ''"
                target="_blank"
                rel="noopener noreferrer"
                >{{ name }} ↗</a
              ><span v-else class="muted">{{ name }}未提供</span></template
            ><el-button @click="linkEditor = true">编辑入口</el-button>
          </div>
          <p class="muted">
            点击链接仅打开原站，不更新最后查看时间，也不记录投递。
          </p>
        </section>
        <section class="panel">
          <h2>我已在官网查看，进度无变化</h2>
          <p>最后查看：{{ app.data.value.last_checked_at || "尚未确认" }}</p>
          <el-input
            v-model="observed"
            placeholder="原站显示的状态"
            aria-label="官网状态"
          /><el-button style="margin-top: 12px" @click="check"
            >确认已查看，阶段不变</el-button
          >
        </section></el-tab-pane
      >
      <el-tab-pane label="投递材料与准备" name="materials" lazy
        ><ManualMaterialForm
          :application-id="id"
          :revision="app.data.value.revision"
          @saved="refresh" />
        <section class="panel">
          <h2>锁定的实际投递</h2>
          <SubmissionSnapshot
            v-for="submission in submissions.data.value?.items"
            :key="submission.id"
            :submission="submission"
            :profiles="profile.data.value?.versions ?? []"
          />
          <p
            v-for="submission in submissions.data.value?.items"
            :key="submission.id"
          >
            {{ submission.submitted_at }} · {{ submission.channel }} ·
            {{
              submission.missing_materials
                ? "历史材料未知"
                : `资料版本 ${submission.profile_version_id}`
            }}<br />简历版本：{{ submission.resume_version_id || "未保存" }}
          </p>
          <p v-if="!submissions.data.value?.items.length" class="muted">
            未记录实际提交；最新版简历不会自动当作历史材料。
          </p>
          <h3>显式切换下一次准备基准</h3>
          <el-select v-model="basisJobId" placeholder="选择岗位版本"
            ><el-option
              v-for="job in jobs.data.value?.items"
              :key="job.id"
              :value="job.current_version_id ?? job.id"
              :label="job.current?.data.title ?? '岗位'" /></el-select
          ><el-select v-model="profileId" clearable placeholder="选择资料版本"
            ><el-option
              v-for="version in profile.data.value?.versions.filter(
                (v) => !v.unavailable,
              )"
              :key="version.id"
              :value="version.id"
              :label="version.created_at + ' · ' + version.reason" /></el-select
          ><el-button @click="changeBasis">使用所选版本准备</el-button>
          <p class="muted">切换后旧待审批草稿失效，不改变历史投递。</p>
        </section>
        <BundleCard
          v-for="bundle in bundles.data.value?.items"
          :key="bundle.id"
          :bundle="bundle"
          @saved="refresh"
      /></el-tab-pane>
      <el-tab-pane label="考核安排" name="rounds" lazy
        ><article
          v-for="row in rounds.data.value?.items"
          :key="row.id"
          class="panel"
        >
          <h2>{{ row.order }} · {{ row.name }}</h2>
          <p>
            {{ label(row.status) }} ·
            {{ row.planned_at ? formatDate(row.planned_at) : "时间待定" }} ·
            {{ row.location }}
          </p>
          <el-button @click="editRound(row)">改期 / 记录结果</el-button
          ><RouterLink
            :to="{ path: '/study', query: { application: id, round: row.id } }"
            >为这一轮准备练习 →</RouterLink
          >
        </article>
        <p v-if="!rounds.data.value?.items.length" class="panel empty">
          没有固定轮次要求，可直接录入技术面。
        </p></el-tab-pane
      >
      <el-tab-pane label="练习" name="practice" lazy
        ><section class="panel">
          <h2>围绕本次申请准备</h2>
          <RouterLink :to="{ path: '/study', query: { application: id } }"
            >创建或查看本申请的训练包 →</RouterLink
          >
          <p class="muted">
            采用该申请选定的
            JD、实际投递资料与轮次；缺少岗位时请先在材料页选择岗位基准。
          </p>
        </section></el-tab-pane
      ><el-tab-pane label="待办" name="tasks" lazy
        ><article
          v-for="task in tasks.data.value?.items"
          :key="task.id"
          class="panel"
        >
          <h3>{{ task.title }}</h3>
          <p>
            {{ task.status }} · {{ task.due_at || task.due_date || "无截止" }}
          </p>
          <p>{{ task.deliverable }} · 验收：{{ task.acceptance }}</p>
        </article></el-tab-pane
      >
      <el-tab-pane label="历史" name="history" lazy
        ><section class="panel">
          <p v-for="event in events.data.value?.items" :key="event.id">
            {{ event.happened_at }} · {{ event.event_type }} ·
            {{ label(event.from_stage) }} → {{ label(event.to_stage) }}<br />{{
              event.reason
            }}
            · 来源 {{ event.source }}<br /><span class="muted"
              >记录于 {{ event.recorded_at }}</span
            >
          </p>
        </section></el-tab-pane
      ></el-tabs
    >
    <DraftDrawer
      v-model="linkEditor"
      title="编辑外部入口"
      :busy="busy"
      :dirty="linksDirty"
    >
      <el-alert v-if="error" :title="error" type="error" />
      <div v-if="error" class="toolbar">
        <el-button @click="refresh">重新读取入口，保留草稿</el-button
        ><el-button @click="discardLinks">放弃入口草稿并载入最新</el-button>
      </div>
      <el-form label-position="top"
        ><el-form-item
          v-for="[field, label] in [
            ['job_url', '岗位详情'],
            ['apply_url', '实际投递'],
            ['progress_url', '官网进度'],
          ] as const"
          :key="field"
          :label="label"
          ><el-input v-model="links[field]" /><a
            v-if="app.data.value[field]"
            :href="app.data.value[field] ?? ''"
            target="_blank"
            rel="noopener noreferrer"
            >打开入口 ↗</a
          ></el-form-item
        ><el-form-item label="导航说明"
          ><el-input v-model="links.navigation_hint" /></el-form-item
        ><el-button @click="saveEntrance">保存入口</el-button></el-form
      >
    </DraftDrawer>
    <DraftDrawer
      :dirty="inputsDirty"
      :busy="busy"
      :model-value="!!dialog"
      :title="
        dialog === 'submission'
          ? '记录实际提交'
          : dialog === 'round'
            ? '考核安排'
            : '追加阶段事件'
      "
      @update:model-value="!$event && (dialog = '')"
      ><el-alert v-if="error" :title="error" type="error" />
      <div v-if="error" class="toolbar">
        <el-button @click="refresh">重新读取申请状态</el-button
        ><el-button v-if="inputsDirty" @click="discardInputs"
          >放弃本地输入并重新填写</el-button
        >
      </div>
      <el-form v-if="dialog === 'submission'" label-position="top"
        ><el-form-item label="实际提交时间（含时区 ISO 或本地时间）"
          ><el-input v-model="submittedAt" /></el-form-item
        ><el-form-item label="实际使用的资料版本"
          ><el-select
            v-model="profileId"
            clearable
            @change="missing = !profileId"
            ><el-option
              v-for="version in profile.data.value?.versions.filter(
                (v) => !v.unavailable,
              )"
              :key="version.id"
              :label="version.reason + ' · ' + version.created_at"
              :value="version.id" /></el-select></el-form-item
        ><el-checkbox v-model="missing">历史材料未知 / 待补录</el-checkbox>
        <p>
          <el-checkbox v-model="confirmed">我确认已在外部真实提交</el-checkbox>
        </p>
        <el-button
          type="primary"
          :loading="busy"
          :disabled="!confirmed"
          @click="submit"
          >保存投递快照</el-button
        ></el-form
      >
      <el-form v-if="dialog === 'round'" label-position="top"
        ><el-form-item label="轮次名称"
          ><el-input v-model="round.name" aria-label="轮次名称" /></el-form-item
        ><el-form-item label="类型"
          ><el-select v-model="round.type"
            ><el-option
              v-for="value in [
                'assessment',
                'take_home',
                'technical',
                'business',
                'hr',
                'other',
              ]"
              :key="value"
              :value="value" /></el-select></el-form-item
        ><el-form-item label="预计时间"
          ><el-date-picker
            v-model="round.planned_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            aria-label="考核时间" /></el-form-item
        ><el-form-item label="结果 / 状态"
          ><el-select v-model="round.status"
            ><el-option
              v-for="value in [
                'pending',
                'scheduled',
                'completed_waiting_result',
                'passed',
                'failed',
                'cancelled',
                'skipped',
              ]"
              :key="value"
              :value="value" /></el-select></el-form-item
        ><el-checkbox v-model="round.reminders_enabled"
          >为这轮考核建立站内待办</el-checkbox
        ><el-button type="primary" :loading="busy" @click="saveRound"
          >保存考核</el-button
        ></el-form
      >
      <el-form v-if="dialog === 'stage'" label-position="top"
        ><el-form-item label="事件类型"
          ><el-select v-model="eventType"
            ><el-option value="advance" label="前进" /><el-option
              value="correction"
              label="更正 / 回退" /><el-option
              value="reopen"
              label="重开" /><el-option
              value="note"
              label="备注" /></el-select></el-form-item
        ><el-form-item label="目标阶段"
          ><el-select v-model="target"
            ><el-option
              v-for="value in [
                'interested',
                'preparing',
                'submitted',
                'assessment',
                'offer',
                'onboarding',
                'closed',
              ]"
              :key="value"
              :value="value" /></el-select></el-form-item
        ><el-form-item label="原因 / 实际依据"
          ><el-input v-model="reason" type="textarea" /></el-form-item
        ><el-form-item v-if="target === 'closed'" label="未完成待办"
          ><el-select v-model="taskAction"
            ><el-option value="keep" label="保留" /><el-option
              value="cancel"
              label="取消" /><el-option
              value="detach"
              label="转普通学习任务" /></el-select></el-form-item
        ><el-button type="primary" :loading="busy" @click="stage"
          >追加事件</el-button
        >
        <p class="muted">
          已投递、考核、Offer 与接受阶段需要对应真实记录。
        </p></el-form
      ></DraftDrawer
    ></template
  >
</template>
