import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Button, Chip, IconButton, Stack, Tooltip, Typography } from "@mui/material";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import ShareOutlinedIcon from "@mui/icons-material/ShareOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import {
  createSessionWebSocket,
  sendInterrupt,
  sendMessage,
} from "../api";
import { useI18n } from "../i18n/LanguageContext";
import {
  terminalColors,
  toolbarButtonSx,
  toolbarChipSx,
  toolbarIconButtonSx,
} from "../theme";
import type {
  ActivityMode,
  EnvMode,
  I18nStrings,
  PresenceStats,
  PromptSet,
  ServerEvent,
  StepRecord,
  TerminalLine,
  TodoItem,
  UpdateEvent,
} from "../types";
import { InputBar } from "./InputBar";
import { StreamingLine } from "./StreamingLine";
import { WorkspaceEditor } from "./WorkspaceEditor";
import { WorkspaceViewer } from "./WorkspaceViewer";
import { Timeline } from "./Timeline";
import { Todos } from "./Todos";

interface TerminalProps {
  sessionId: string;
  envMode: EnvMode;
  promptSet: PromptSet;
  presence: PresenceStats;
  onExit: () => void;
  onOpenSidebar?: () => void;
  shareMode?: boolean;
}

let lineCounter = 0;
function nextLineId(prefix: string): string {
  lineCounter += 1;
  return `${prefix}-${lineCounter}`;
}

export function Terminal({
  sessionId,
  envMode,
  promptSet,
  presence,
  onExit,
  onOpenSidebar,
  shareMode,
}: TerminalProps) {
  const { t } = useI18n();
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [steps, setSteps] = useState<Record<string, StepRecord>>({});
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [todosLineId, setTodosLineId] = useState<string | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [activityMode, setActivityMode] = useState<ActivityMode>("idle");
  const [i18n, setI18n] = useState<I18nStrings | null>(null);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [frameIndex, setFrameIndex] = useState(0);
  const [editorOpen, setEditorOpen] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const lastWorkspaceSummaryRef = useRef<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stepLineIdsRef = useRef<Record<string, string>>({});

  const applyUpdate = useCallback((event: UpdateEvent) => {
    if (Object.keys(event.steps).length) {
      setSteps((prev) => ({ ...prev, ...event.steps }));
    }

    if (event.timeline.length > 0) {
      setLines((prev) => {
        let next = prev;
        const toAppend: TerminalLine[] = [];

        for (const entry of event.timeline) {
          if (entry.kind === "step" && entry.step_id) {
            const step = event.steps[entry.step_id];
            if (step) {
              const existingLineId = stepLineIdsRef.current[step.step_id];
              if (existingLineId) {
                next = next.map((line) =>
                  line.id === existingLineId ? { ...line, step } : line,
                );
                const pendingIdx = toAppend.findIndex((line) => line.id === existingLineId);
                if (pendingIdx >= 0) {
                  toAppend[pendingIdx] = { ...toAppend[pendingIdx], step };
                }
              } else {
                const lineId = nextLineId("step");
                stepLineIdsRef.current[step.step_id] = lineId;
                toAppend.push({ id: lineId, kind: "step", step });
              }
              continue;
            }
          }

          if (entry.kind === "user") {
            const last = toAppend.length > 0 ? toAppend[toAppend.length - 1] : next[next.length - 1];
            if (last?.kind === "user" && last.text === entry.text) {
              continue;
            }
          }

          toAppend.push({
            id: nextLineId(entry.kind),
            kind: entry.kind,
            text: entry.text,
          });
        }

        return toAppend.length > 0 ? [...next, ...toAppend] : next;
      });
    }

    if (event.todos.length) {
      setTodos(event.todos);
      setTodosLineId((prev) => prev ?? nextLineId("todos"));
    }

    if (event.streaming_assistant !== null && event.streaming_assistant !== undefined) {
      setStreamingText(event.streaming_assistant);
    }

    if (event.activity_mode) {
      setActivityMode(event.activity_mode);
      setBusy(event.activity_mode !== "idle");
    } else if (event.activity_mode === null) {
      // keep current
    }

    if (event.workspace_summary) {
      const prefix = event.workspace_prefix ?? "workspace";
      const summary = `${prefix} · ${event.workspace_summary}`;
      if (summary !== lastWorkspaceSummaryRef.current) {
        lastWorkspaceSummaryRef.current = summary;
        setLines((prev) => [
          ...prev,
          { id: nextLineId("system"), kind: "system", text: summary },
        ]);
      }
    }
  }, []);

  const handleServerEvent = useCallback(
    (event: ServerEvent) => {
      if (event.type === "banner") {
        setI18n(event.i18n);
        lastWorkspaceSummaryRef.current = event.workspace_summary;
        setLines([
          {
            id: nextLineId("banner"),
            kind: "banner",
            text: `${event.title}  workspace=${event.workspace_root}`,
          },
          {
            id: nextLineId("banner"),
            kind: "system",
            text: event.workspace_summary,
          },
          {
            id: nextLineId("banner"),
            kind: "system",
            text: event.i18n.banner_hint,
          },
        ]);
        return;
      }

      if (event.type === "step_refresh") {
        setSteps((prev) => ({ ...prev, [event.step.step_id]: event.step }));
        const lineId = stepLineIdsRef.current[event.step.step_id];
        if (lineId) {
          setLines((prev) =>
            prev.map((line) =>
              line.id === lineId ? { ...line, step: event.step } : line,
            ),
          );
        }
        return;
      }

      if (event.type === "update") {
        if (event.activity_mode === "idle") {
          setBusy(false);
          setStreamingText("");
          setActivityMode("idle");
        }
        applyUpdate(event);
      }
    },
    [applyUpdate],
  );

  useEffect(() => {
    lineCounter = 0;
    stepLineIdsRef.current = {};
    setLines([]);
    setSteps({});
    setTodos([]);
    setTodosLineId(null);
    setStreamingText("");
    setActivityMode("idle");
    setBusy(false);
    lastWorkspaceSummaryRef.current = null;

    const ws = createSessionWebSocket(
      sessionId,
      handleServerEvent,
      () => setConnected(false),
      () => setConnected(false),
    );
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, handleServerEvent]);

  useEffect(() => {
    if (!busy && activityMode === "idle") return;
    const timer = window.setInterval(() => {
      setFrameIndex((prev) => prev + 1);
    }, 120);
    return () => window.clearInterval(timer);
  }, [busy, activityMode]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [lines, streamingText, todos, busy, activityMode]);

  useEffect(() => {
    if (shareMode) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && wsRef.current?.readyState === WebSocket.OPEN) {
        sendInterrupt(wsRef.current);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [shareMode]);

  const handleSubmit = () => {
    const text = input.trim();
    if (
      !text ||
      busy ||
      !wsRef.current ||
      wsRef.current.readyState !== WebSocket.OPEN
    ) {
      return;
    }
    if (["exit", "quit", "/exit", "/quit"].includes(text.toLowerCase())) {
      sendMessage(wsRef.current, text);
      setInput("");
      window.setTimeout(onExit, 300);
      return;
    }
    setLines((prev) => {
      const last = prev[prev.length - 1];
      if (last?.kind === "user" && last.text === text) {
        return prev;
      }
      return [...prev, { id: nextLineId("user"), kind: "user", text }];
    });
    setBusy(true);
    sendMessage(wsRef.current, text);
    setInput("");
  };

  const handleCopySessionId = async () => {
    try {
      await navigator.clipboard.writeText(sessionId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/share/${sessionId}`);
      setShareCopied(true);
      window.setTimeout(() => setShareCopied(false), 1500);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleInterrupt = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendInterrupt(wsRef.current);
    }
  };

  const activityLabels = i18n?.activity_labels ?? {
    thinking: "thinking",
    tool: "running tool",
    streaming: "streaming",
  };

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        minWidth: 0,
      }}
    >
      <Box
        sx={{
          px: 2,
          py: { xs: 0.75, sm: 1 },
          borderBottom: `1px solid ${terminalColors.border}`,
          bgcolor: terminalColors.panel,
        }}
      >
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          gap={1}
          flexWrap="wrap"
        >
          {!shareMode && (
            <Stack
              direction="row"
              alignItems="center"
              gap={0.75}
              flexWrap="wrap"
              useFlexGap
              sx={{ minWidth: 0, flex: 1 }}
            >
              {onOpenSidebar && (
                <IconButton
                  size="small"
                  onClick={onOpenSidebar}
                  aria-label={t("terminal.openSidebar")}
                  sx={toolbarIconButtonSx}
                >
                  <MenuIcon sx={{ fontSize: 16 }} />
                </IconButton>
              )}
              <Chip
                size="small"
                variant="outlined"
                label={copied ? t("terminal.copied") : sessionId}
                onClick={() => void handleCopySessionId()}
                sx={{
                  ...toolbarChipSx,
                  fontFamily: "monospace",
                  color: terminalColors.text,
                  cursor: "pointer",
                  maxWidth: { xs: 160, sm: 320 },
                  "&:hover": {
                    borderColor: terminalColors.cyan,
                    bgcolor: "rgba(57, 197, 207, 0.08)",
                  },
                  "& .MuiChip-label": {
                    ...toolbarChipSx["& .MuiChip-label"],
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  },
                }}
              />
              <Chip
                size="small"
                variant="outlined"
                label={envMode}
                sx={{ ...toolbarChipSx, display: { xs: "none", sm: "inline-flex" } }}
              />
              <Chip
                size="small"
                variant="outlined"
                label={promptSet}
                sx={{ ...toolbarChipSx, display: { xs: "none", sm: "inline-flex" } }}
              />
              {busy && (
                <Chip
                  size="small"
                  variant="outlined"
                  label={t("terminal.reasoning")}
                  sx={{
                    ...toolbarChipSx,
                    color: terminalColors.yellow,
                    borderColor: "rgba(210, 153, 34, 0.55)",
                    bgcolor: "rgba(210, 153, 34, 0.06)",
                  }}
                />
              )}
              <Chip
                size="small"
                variant="outlined"
                label={t("terminal.onlineSessions", { sessions: presence.online_sessions })}
                sx={{
                  ...toolbarChipSx,
                  color: terminalColors.green,
                  borderColor: "rgba(63, 185, 80, 0.45)",
                  bgcolor: "rgba(63, 185, 80, 0.06)",
                  display: { xs: "none", sm: "inline-flex" },
                }}
              />
            </Stack>
          )}
          <Stack direction="row" spacing={0.75} sx={{ display: { xs: "flex", sm: "none" } }}>
            {!shareMode && (
              <Tooltip title={t("terminal.shareTooltip")} arrow>
                <IconButton
                  size="small"
                  aria-label={t("terminal.shareTooltip")}
                  onClick={() => void handleShare()}
                  sx={toolbarIconButtonSx}
                >
                  <ShareOutlinedIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            )}
            <IconButton
              size="small"
              aria-label={t("terminal.view")}
              onClick={() => setViewerOpen(true)}
              sx={toolbarIconButtonSx}
            >
              <VisibilityOutlinedIcon sx={{ fontSize: 16 }} />
            </IconButton>
            <IconButton
              size="small"
              aria-label={t("terminal.edit")}
              onClick={() => setEditorOpen(true)}
              sx={toolbarIconButtonSx}
            >
              <EditOutlinedIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Stack>
          <Stack direction="row" spacing={0.75} sx={{ display: { xs: "none", sm: "flex" } }}>
            {!shareMode && (
              <Tooltip title={shareCopied ? t("terminal.shareCopied") : t("terminal.shareTooltip")} arrow>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => void handleShare()}
                  sx={toolbarButtonSx}
                >
                  <ShareOutlinedIcon sx={{ fontSize: 16, mr: 0.5 }} />
                  {t("terminal.shareTooltip")}
                </Button>
              </Tooltip>
            )}
            <Button
              size="small"
              variant="outlined"
              onClick={() => setViewerOpen(true)}
              sx={toolbarButtonSx}
            >
              {t("terminal.view")}
            </Button>
            <Button
              size="small"
              variant="outlined"
              onClick={() => setEditorOpen(true)}
              sx={toolbarButtonSx}
            >
              {t("terminal.edit")}
            </Button>
          </Stack>
        </Stack>
      </Box>

      <Box
        ref={scrollRef}
        sx={{
          flex: 1,
          overflow: "auto",
          p: 2,
          fontFamily: "inherit",
        }}
      >
        {lines.map((line) => {
          if (line.kind === "banner" || line.kind === "system" || line.kind === "user" || line.kind === "assistant" || line.kind === "error" || line.kind === "progress") {
            return (
              <Timeline
                key={line.id}
                entry={{
                  kind: line.kind === "banner" ? "system" : line.kind,
                  text: line.text ?? "",
                  step_id: null,
                }}
              />
            );
          }
          if (line.kind === "step" && line.step) {
            return <Timeline key={line.id} entry={{ kind: "step", text: "", step_id: line.step.step_id }} step={line.step} />;
          }
          return null;
        })}

        {todos.length > 0 && todosLineId && (
          <Todos title={i18n?.plan_title ?? "Plan"} items={todos} />
        )}

        {(streamingText || busy) && (
          <StreamingLine
            text={streamingText}
            activityMode={activityMode === "idle" && busy ? "thinking" : (activityMode ?? "thinking")}
            activityLabels={activityLabels}
            frameIndex={frameIndex}
          />
        )}

        {!connected && (
          <Typography sx={{ color: terminalColors.yellow, mt: 1 }}>
            {t("terminal.connecting")}
          </Typography>
        )}
      </Box>

      {!shareMode && (
        <InputBar
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          disabled={!connected}
          busy={busy}
          onInterrupt={handleInterrupt}
        />
      )}
      <WorkspaceEditor
        sessionId={sessionId}
        envMode={envMode}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        readOnly={shareMode}
      />
      <WorkspaceViewer
        sessionId={sessionId}
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
      />
    </Box>
  );
}
