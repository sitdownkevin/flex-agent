export type PromptSet =
  | "baseline"
  | "baseline_en"
  | "baseline_oneshot"
  | "baseline_fewshot";

export type EnvMode = "env" | "byok";

export interface EnvOverrides {
  OPENAI_API_KEY?: string;
  OPENAI_BASE_URL?: string;
  OPENAI_MODEL?: string;
  OPENAI_MODEL_PRO?: string;
}

export interface CreateSessionParams {
  language: "zh" | "en";
  prompt_set: PromptSet;
  mode: EnvMode;
  overrides?: EnvOverrides;
}

export type TimelineKind = "user" | "assistant" | "step" | "system" | "error" | "progress";

export type StepStatus = "running" | "done" | "error";

export type TodoStatus = "pending" | "in_progress" | "completed";

export type ActivityMode = "idle" | "thinking" | "streaming" | "tool" | null;

export interface TimelineEntry {
  kind: TimelineKind;
  text: string;
  step_id: string | null;
}

export interface StepRecord {
  step_id: string;
  tool_name: string;
  label: string;
  summary: string;
  status: StepStatus;
  result_preview: string;
}

export interface TodoItem {
  content: string;
  status: TodoStatus;
}

export interface I18nStrings {
  banner_hint: string;
  plan_title: string;
  workspace_prefix: string;
  activity_labels: Record<string, string>;
  interrupted: string;
  recursion_limit_reached: string;
  bye: string;
  running: string;
}

export interface BannerPayload {
  title: string;
  workspace_root: string;
  workspace_summary: string;
  i18n: I18nStrings;
}

export interface UpdateEvent {
  type: "update";
  timeline: TimelineEntry[];
  steps: Record<string, StepRecord>;
  todos: TodoItem[];
  streaming_assistant: string | null;
  activity_mode: ActivityMode;
  workspace_summary?: string;
  workspace_prefix?: string;
}

export interface BannerEvent extends BannerPayload {
  type: "banner";
}

export interface StepRefreshEvent {
  type: "step_refresh";
  step: StepRecord;
}

export type ServerEvent = UpdateEvent | BannerEvent | StepRefreshEvent;

export interface SessionSummary {
  id: string;
  language: string;
  created_at: string | null;
  status_summary: string;
  workspace_root: string;
  env_mode: EnvMode;
  prompt_set: PromptSet;
}

export interface SessionDetail {
  id: string;
  language: string;
  env_mode: EnvMode;
  prompt_set: PromptSet;
  banner: BannerPayload;
  status: Record<string, unknown>;
  meta?: Record<string, unknown> | null;
}

export interface TerminalLine {
  id: string;
  kind: TimelineKind | "banner" | "todos" | "streaming";
  text?: string;
  step?: StepRecord;
  todos?: TodoItem[];
  planTitle?: string;
}
