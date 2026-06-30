import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Button, Chip, IconButton, Stack, Typography } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import {
  createSessionWebSocket,
  sendInterrupt,
  sendMessage,
} from "../api";
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
  PromptSet,
  ServerEvent,
  StepRecord,
  TerminalLine,
  TodoItem,
  UpdateEvent,
} from "../types";
import { InputBar } from "./InputBar";
import { StreamingLine } from "./StreamingLine";
import { TaskBackgroundEditor } from "./TaskBackgroundEditor";
import { Timeline } from "./Timeline";
import { Todos } from "./Todos";

interface TerminalProps {
  sessionId: string;
  envMode: EnvMode;
  promptSet: PromptSet;
  onExit: () => void;
  onOpenSidebar?: () => void;
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
  onExit,
  onOpenSidebar,
}: TerminalProps) {
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
  const [copied, setCopied] = useState(false);
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
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && wsRef.current?.readyState === WebSocket.OPEN) {
        sendInterrupt(wsRef.current);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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

  const handleInterrupt = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      sendInterrupt(wsRef.current);
    }
  };

  const activityLabels = i18n?.activity_labels ?? {
    thinking: "Agent 思考中",
    tool: "执行工具",
    streaming: "生成回复",
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
          py: 1,
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
                aria-label="打开侧边栏"
                sx={toolbarIconButtonSx}
              >
                <MenuIcon sx={{ fontSize: 16 }} />
              </IconButton>
            )}
            <Chip
              size="small"
              variant="outlined"
              label={copied ? "已复制" : sessionId}
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
            <Chip size="small" variant="outlined" label={envMode} sx={toolbarChipSx} />
            <Chip size="small" variant="outlined" label={promptSet} sx={toolbarChipSx} />
            {busy && (
              <Chip
                size="small"
                variant="outlined"
                label="● 推理中"
                sx={{
                  ...toolbarChipSx,
                  color: terminalColors.yellow,
                  borderColor: "rgba(210, 153, 34, 0.55)",
                  bgcolor: "rgba(210, 153, 34, 0.06)",
                }}
              />
            )}
          </Stack>
          <Button
            size="small"
            variant="outlined"
            onClick={() => setEditorOpen(true)}
            sx={toolbarButtonSx}
          >
            编辑 task_background
          </Button>
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
            连接中…
          </Typography>
        )}
      </Box>

      <InputBar
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        disabled={!connected}
        busy={busy}
        onInterrupt={handleInterrupt}
      />
      <TaskBackgroundEditor
        sessionId={sessionId}
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
      />
    </Box>
  );
}
