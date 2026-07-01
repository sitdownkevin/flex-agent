export type UiLang = "zh" | "en";

export const UI_LANGS: UiLang[] = ["zh", "en"];
export const DEFAULT_UI_LANG: UiLang = "zh";
export const UI_LANG_STORAGE_KEY = "flex-agent:ui-lang";

/**
 * Translation dictionary. Keys are dotted paths grouped by feature.
 * Missing keys fall back to the key itself (rendered as-is) so that
 * untranslated strings stay visible instead of disappearing.
 */
export const translations: Record<UiLang, Record<string, string>> = {
  zh: {
    // EntryScreen
    "entry.brandTitle": "CODE: COnstruct Development Engine",
    "entry.subtitle": "COnstruct Development Engine",
    "entry.githubTooltip": "GitHub 仓库",
    "entry.presenceOnline": "当前 {sessions} 人",
    "entry.recentTitle": "本机最近使用",
    "entry.recentCollapseTooltip": "折叠",
    "entry.recentExpandTooltip": "展开",
    "entry.copyTooltip": "复制工作区 ID",
    "entry.openTitle": "打开已有工作区",
    "entry.openButton": "打开",
    "entry.openErrorEmpty": "请输入工作区 ID",
    "entry.openErrorFailed": "打开失败，请确认工作区 ID 是否正确",
    "entry.or": "或",
    "entry.createTitle": "新建工作区",
    "entry.modeLabel": "模式",
    "entry.modeEnv": "DeekSeep V4 Flash (Default)",
    "entry.modeByok": "自定义 API Key (BYOK)",
    "entry.show": "显示",
    "entry.hide": "隐藏",
    "entry.promptSetLabel": "基准",
    "entry.hints.baseline": "中文 baseline prompt set",
    "entry.hints.baseline_en": "English baseline prompt set",
    "entry.hints.baseline_oneshot": "中文 baseline one-shot variant",
    "entry.hints.baseline_fewshot": "中文 baseline few-shot variant",
    "entry.hints.baseline_oneshot_en": "English baseline one-shot variant",
    "entry.hints.baseline_fewshot_en": "English baseline few-shot variant",
    "entry.createButton": "创建并进入",
    "entry.createError": "创建失败",

    // Sidebar
    "sidebar.home": "首页",
    "sidebar.recentTitle": "本机最近使用",
    "sidebar.empty": "暂无记录",
    "sidebar.deleteSession": "删除工作区",
    "sidebar.githubTooltip": "GitHub 仓库",
    "sidebar.confirmTitle": "删除工作区",
    "sidebar.confirmMessage": "确认删除工作区 {id}？此操作不可撤销。",
    "sidebar.confirmLabel": "删除",

    // Terminal
    "terminal.openSidebar": "打开侧边栏",
    "terminal.copied": "已复制",
    "terminal.reasoning": "● 推理中",
    "terminal.onlineSessions": "当前 {sessions} 人",
    "terminal.view": "查看",
    "terminal.edit": "编辑",
    "terminal.connecting": "连接中…",

    // InputBar
    "input.placeholderBusy": "Agent 推理中，请稍候…",
    "input.placeholderIdle": "输入 open coding 任务或 slash 命令…",
    "input.stop": "停止",
    "input.send": "发送",

    // WorkspaceEditor
    "editor.title": "编辑工作区文件",
    "editor.download": "下载",
    "editor.alert": "修改会自动保存",
    "editor.hintSwitch": "切换 Tab 或关闭窗口时若有未保存改动会自动保存。",
    "editor.saving": "保存中…",
    "editor.saved": "已保存",
    "editor.saveFailed": "保存失败",
    "editor.unsaved": "未保存",
    "editor.synced": "已同步",
    "editor.loading": "加载中…",
    "editor.loadFailed": "加载失败",
    "editor.savedReload": "已保存 · agent 已重载",
    "editor.savedReloadReset": "已保存 · agent 已重载，对话记忆会被重置",
    "editor.byokTab": "BYOK",
    "editor.byokHint": "修改后点击保存，agent 会重载以应用新的 API 配置。建议重新打开会话以确保生效。",
    "editor.byokSave": "保存",
    "editor.byokSaving": "保存中…",
    "editor.byokSaved": "已保存 · agent 已重载",
    "editor.byokSaveFailed": "保存失败",
    "editor.byokLoadFailed": "加载失败",

    // WorkspaceViewer
    "viewer.title": "查看工作区",
    "viewer.loadFailed": "加载失败",
    "viewer.tabOverview": "概览",
    "viewer.tabCodebook": "代码本",
    "viewer.tabCoding": "编码结果",
    "viewer.tabCorpus": "语料预览",
    "viewer.tabEval": "评测",
    "viewer.statTotal": "语料总数",
    "viewer.statCoded": "已编码",
    "viewer.statQueue": "队列剩余",
    "viewer.statDimensions": "维度数",
    "viewer.statEvalOpen": "Open 评测",
    "viewer.statEvalAxial": "Axial 评测",
    "viewer.partition": "数据划分",
    "viewer.qualityWarnings": "质量告警",
    "viewer.codebookEmpty": "尚未生成代码本。运行概念归纳（Construct Induction）后将在此展示维度。",
    "viewer.codingEmpty": "尚无编码结果。运行开放式编码（Open Coding）后将在此展示。",
    "viewer.corpusEmpty": "语料文件为空或尚未加载。",
    "viewer.corpusCount": "共 {total} 条语料，预览前 {count} 条",
    "viewer.codingLabels": "{count} 标签",
    "viewer.colLabel": "标签",
    "viewer.colEvidence": "证据",
    "viewer.colDimension": "维度",
    "viewer.evalOpenTitle": "Open Coding 评测",
    "viewer.evalAxialTitle": "Axial Coding 评测",
    "viewer.evalEmpty": "无评测数据。运行 /eval:open 或 /eval:axial 后将在此展示。",
    "viewer.evalNoMacro": "评测已完成，但暂无可展示的 macro 指标。",
    "viewer.evalStatus": "状态: {status}",
    "viewer.evalMode": "模式: {mode}",
    "viewer.evalCoded": "已编码: {count}",
    "viewer.metricKeyword": "关键词匹配",
    "viewer.metricSemantic": "语义对齐",
    "viewer.matchBoth": "共同匹配 ({count})",
    "viewer.matchAgentOnly": "仅 Agent ({count})",
    "viewer.matchHumanOnly": "仅人工 ({count})",

    // ConfirmDialog
    "confirm.confirm": "确认",
    "confirm.cancel": "取消",

    // StreamingLine / Timeline
    "stream.running": "running",
    "timeline.errorPrefix": "error: ",

    // App
    "app.deleteFailed": "删除工作区失败",
    "app.statusSummary": "texts={texts} · coded={coded} · queue={queue} · dimensions={dimensions}",
  },
  en: {
    // EntryScreen
    "entry.brandTitle": "CODE: COnstruct Development Engine",
    "entry.subtitle": "COnstruct Development Engine",
    "entry.githubTooltip": "GitHub repository",
    "entry.presenceOnline": "Currently {sessions} online",
    "entry.recentTitle": "Recent on this machine",
    "entry.recentCollapseTooltip": "Collapse",
    "entry.recentExpandTooltip": "Expand",
    "entry.copyTooltip": "Copy session_id",
    "entry.openTitle": "Open an existing workspace",
    "entry.openButton": "Open",
    "entry.openErrorEmpty": "Please enter a session_id",
    "entry.openErrorFailed": "Failed to open; check the session_id and try again",
    "entry.or": "or",
    "entry.createTitle": "Create a new workspace",
    "entry.modeLabel": "Mode",
    "entry.modeEnv": "DeekSeep V4 Flash (Default)",
    "entry.modeByok": "Bring Your Own Key (BYOK)",
    "entry.show": "Show",
    "entry.hide": "Hide",
    "entry.promptSetLabel": "Benchmark",
    "entry.hints.baseline": "Chinese baseline prompt set",
    "entry.hints.baseline_en": "English baseline prompt set",
    "entry.hints.baseline_oneshot": "Chinese baseline one-shot variant",
    "entry.hints.baseline_fewshot": "Chinese baseline few-shot variant",
    "entry.hints.baseline_oneshot_en": "English baseline one-shot variant",
    "entry.hints.baseline_fewshot_en": "English baseline few-shot variant",
    "entry.createButton": "Create & enter",
    "entry.createError": "Failed to create",

    // Sidebar
    "sidebar.home": "Home",
    "sidebar.recentTitle": "Recent on this machine",
    "sidebar.empty": "No records",
    "sidebar.deleteSession": "Delete session",
    "sidebar.githubTooltip": "GitHub repository",
    "sidebar.confirmTitle": "Delete session",
    "sidebar.confirmMessage": "Delete session {id}? This cannot be undone.",
    "sidebar.confirmLabel": "Delete",

    // Terminal
    "terminal.openSidebar": "Open sidebar",
    "terminal.copied": "Copied",
    "terminal.reasoning": "● reasoning",
    "terminal.onlineSessions": "Currently {sessions} online",
    "terminal.view": "View",
    "terminal.edit": "Edit",
    "terminal.connecting": "Connecting…",

    // InputBar
    "input.placeholderBusy": "Agent is reasoning, please wait…",
    "input.placeholderIdle": "Enter an open-coding task or slash command…",
    "input.stop": "Stop",
    "input.send": "Send",

    // WorkspaceEditor
    "editor.title": "Edit workspace files",
    "editor.download": "Download",
    "editor.alert": "Changes auto-save",
    "editor.hintSwitch": "Unsaved changes are auto-saved when you switch tabs or close the window.",
    "editor.saving": "Saving…",
    "editor.saved": "Saved",
    "editor.saveFailed": "Save failed",
    "editor.unsaved": "Unsaved",
    "editor.synced": "In sync",
    "editor.loading": "Loading…",
    "editor.loadFailed": "Failed to load",
    "editor.savedReload": "Saved · agent reloaded",
    "editor.savedReloadReset": "Saved · agent reloaded; conversation memory is reset",
    "editor.byokTab": "BYOK",
    "editor.byokHint": "Save to reload the agent with the new API config. Reopening the session is recommended to ensure it takes effect.",
    "editor.byokSave": "Save",
    "editor.byokSaving": "Saving…",
    "editor.byokSaved": "Saved · agent reloaded",
    "editor.byokSaveFailed": "Save failed",
    "editor.byokLoadFailed": "Failed to load",

    // WorkspaceViewer
    "viewer.title": "View workspace",
    "viewer.loadFailed": "Failed to load",
    "viewer.tabOverview": "Overview",
    "viewer.tabCodebook": "Codebook",
    "viewer.tabCoding": "Coding results",
    "viewer.tabCorpus": "Corpus preview",
    "viewer.tabEval": "Evaluation",
    "viewer.statTotal": "Total texts",
    "viewer.statCoded": "Coded",
    "viewer.statQueue": "Queue left",
    "viewer.statDimensions": "Dimensions",
    "viewer.statEvalOpen": "Open eval",
    "viewer.statEvalAxial": "Axial eval",
    "viewer.partition": "Partition",
    "viewer.qualityWarnings": "Quality warnings",
    "viewer.codebookEmpty": "No codebook yet. Run Construct Induction to see dimensions here.",
    "viewer.codingEmpty": "No coding results yet. Run Open Coding to see them here.",
    "viewer.corpusEmpty": "Corpus file is empty or not loaded.",
    "viewer.corpusCount": "{total} texts total, previewing first {count}",
    "viewer.codingLabels": "{count} labels",
    "viewer.colLabel": "Label",
    "viewer.colEvidence": "Evidence",
    "viewer.colDimension": "Dimension",
    "viewer.evalOpenTitle": "Open Coding evaluation",
    "viewer.evalAxialTitle": "Axial Coding evaluation",
    "viewer.evalEmpty": "No evaluation data. Run /eval:open or /eval:axial to populate this view.",
    "viewer.evalNoMacro": "Evaluation finished, but no macro metrics are available to display.",
    "viewer.evalStatus": "Status: {status}",
    "viewer.evalMode": "Mode: {mode}",
    "viewer.evalCoded": "Coded: {count}",
    "viewer.metricKeyword": "Keyword match",
    "viewer.metricSemantic": "Semantic alignment",
    "viewer.matchBoth": "Both ({count})",
    "viewer.matchAgentOnly": "Agent only ({count})",
    "viewer.matchHumanOnly": "Human only ({count})",

    // ConfirmDialog / StreamingLine / Timeline
    "confirm.confirm": "Confirm",
    "confirm.cancel": "Cancel",
    "stream.running": "running",
    "timeline.errorPrefix": "error: ",

    // App
    "app.deleteFailed": "Failed to delete session",
    "app.statusSummary": "texts={texts} · coded={coded} · queue={queue} · dimensions={dimensions}",
  },
};

/**
 * Translate a key for the given language, substituting `{name}` placeholders
 * from `vars`. Missing keys fall back to the key itself.
 */
export function translate(
  lang: UiLang,
  key: string,
  vars?: Record<string, string | number>,
): string {
  const table = translations[lang] ?? translations[DEFAULT_UI_LANG];
  let value = table[key];
  if (value === undefined) {
    value = translations[DEFAULT_UI_LANG][key] ?? key;
  }
  if (vars) {
    for (const [name, raw] of Object.entries(vars)) {
      value = value.replace(new RegExp(`\\{${name}\\}`, "g"), String(raw));
    }
  }
  return value;
}
