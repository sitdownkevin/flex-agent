import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import {
  downloadFileUrl,
  getTextFile,
  getSessionEnv,
  saveSessionEnv,
  saveTaskBackground,
  uploadFile,
  type WorkspaceTextPath,
} from "../api";
import { useI18n } from "../i18n/LanguageContext";
import { fontSizes, monoFont, terminalColors } from "../theme";
import type { EnvMode } from "../types";

interface WorkspaceEditorProps {
  sessionId: string;
  envMode: EnvMode;
  open: boolean;
  onClose: () => void;
  readOnly?: boolean;
}

type SaveState = "idle" | "saving" | "saved" | "error";

export type TabSaveStatus = {
  saveState: SaveState;
  dirty: boolean;
};

export interface EditableFileTabHandle {
  flush: () => Promise<void>;
}

const AUTOSAVE_DELAY_MS = 800;

interface EditableFileTabProps {
  sessionId: string;
  open: boolean;
  isActive: boolean;
  loadPath: WorkspaceTextPath;
  save: (sessionId: string, content: string) => Promise<void>;
  downloadUrl?: string;
  savedLabel?: string;
  onStatusChange: (status: TabSaveStatus) => void;
  readOnly?: boolean;
}

const EditableFileTab = forwardRef<EditableFileTabHandle, EditableFileTabProps>(
  function EditableFileTab(
    {
      sessionId,
      open,
      isActive,
      loadPath,
      save,
      downloadUrl,
      savedLabel,
      onStatusChange,
      readOnly,
    },
    ref,
  ) {
    const { t } = useI18n();
    const [content, setContent] = useState("");
    const [loading, setLoading] = useState(false);
    const [saveState, setSaveState] = useState<SaveState>("idle");
    const [error, setError] = useState<string | null>(null);

    const contentRef = useRef("");
    const lastSavedRef = useRef("");
    const dirtyRef = useRef(false);
    const saveTimerRef = useRef<number | null>(null);
    const inFlightRef = useRef(false);
    const loadedRef = useRef(false);

    const reportStatus = (state: SaveState) => {
      onStatusChange({ saveState: state, dirty: dirtyRef.current });
    };

    useEffect(() => {
      contentRef.current = content;
    }, [content]);

    useEffect(() => {
      if (!open || !isActive) return;
      if (loadedRef.current) return;
      setLoading(true);
      setError(null);
      setSaveState("idle");
      void getTextFile(sessionId, loadPath)
        .then((text) => {
          setContent(text);
          contentRef.current = text;
          lastSavedRef.current = text;
          dirtyRef.current = false;
          loadedRef.current = true;
          reportStatus("idle");
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : t("editor.loadFailed"));
        })
        .finally(() => setLoading(false));
    }, [open, isActive, sessionId, loadPath]);

    useEffect(() => {
      if (open) return;
      loadedRef.current = false;
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      setSaveState("idle");
      dirtyRef.current = false;
    }, [open]);

    const runSave = async (value: string) => {
      if (inFlightRef.current) return;
      if (value === lastSavedRef.current) {
        dirtyRef.current = false;
        setSaveState("idle");
        reportStatus("idle");
        return;
      }
      inFlightRef.current = true;
      setSaveState("saving");
      reportStatus("saving");
      try {
        await save(sessionId, value);
        lastSavedRef.current = value;
        dirtyRef.current = false;
        setSaveState("saved");
        reportStatus("saved");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : t("editor.saveFailed"));
        setSaveState("error");
        reportStatus("error");
      } finally {
        inFlightRef.current = false;
      }
    };

    const flush = async () => {
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      const value = contentRef.current;
      if (dirtyRef.current && value !== lastSavedRef.current) {
        await runSave(value);
      }
    };

    useImperativeHandle(ref, () => ({ flush }), [sessionId, save]);

    useEffect(() => {
      if (isActive) return;
      void flush();
    }, [isActive]);

    const scheduleSave = (value: string) => {
      if (value === lastSavedRef.current) {
        dirtyRef.current = false;
        if (saveTimerRef.current !== null) {
          window.clearTimeout(saveTimerRef.current);
          saveTimerRef.current = null;
        }
        setSaveState("idle");
        reportStatus("idle");
        return;
      }
      dirtyRef.current = true;
      setSaveState("idle");
      reportStatus("idle");
      if (saveTimerRef.current !== null) {
        window.clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = window.setTimeout(() => {
        saveTimerRef.current = null;
        void runSave(value);
      }, AUTOSAVE_DELAY_MS);
    };

    if (!isActive) return null;

    return (
      <Box>
        {downloadUrl && (
          <Button
            size="small"
            variant="outlined"
            href={downloadUrl}
            download
            sx={{ mb: 1.5, borderColor: terminalColors.border }}
          >
            {t("editor.download")}
          </Button>
        )}
        {error && (
          <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}
        <TextField
          fullWidth
          multiline
          minRows={12}
          maxRows={24}
          value={content}
          disabled={loading}
          readOnly={readOnly}
          onChange={(event) => {
            const next = event.target.value;
            setContent(next);
            contentRef.current = next;
            if (!readOnly) scheduleSave(next);
          }}
          placeholder={loading ? t("editor.loading") : ""}
          InputProps={{
            sx: {
              fontFamily: monoFont,
              fontSize: fontSizes.md,
              color: terminalColors.text,
            },
          }}
        />
        <Typography
          sx={{
            mt: 1,
            fontSize: fontSizes.sm,
            color: terminalColors.gray,
            opacity: 0.7,
          }}
        >
          {readOnly ? "" : savedLabel}
        </Typography>
      </Box>
    );
  },
);

type TFunction = ReturnType<typeof useI18n>["t"];

interface EditorTab {
  label: string;
  loadPath: WorkspaceTextPath;
  save: (sessionId: string, content: string) => Promise<void>;
  savedLabel: string;
  downloadKind?: "corpus.jsonl" | "corpus_with_labels.jsonl";
  byok?: boolean;
}

function buildTabs(t: TFunction, envMode: EnvMode, readOnly?: boolean): EditorTab[] {
  const fileTabs: EditorTab[] = [
    {
      label: "task_background.md",
      loadPath: "prompts/task_background.md",
      save: saveTaskBackground,
      savedLabel: t("editor.savedReloadReset"),
    },
    {
      label: "corpus.jsonl",
      loadPath: "files/corpus.jsonl",
      save: async (sessionId: string, content: string) => {
        await uploadFile(
          sessionId,
          "corpus.jsonl",
          new File([content], "corpus.jsonl", { type: "application/x-ndjson" }),
        );
      },
      downloadKind: "corpus.jsonl",
      savedLabel: t("editor.savedReload"),
    },
    {
      label: "corpus_with_labels.jsonl",
      loadPath: "files/corpus_with_labels.jsonl",
      save: async (sessionId: string, content: string) => {
        await uploadFile(
          sessionId,
          "corpus_with_labels.jsonl",
          new File([content], "corpus_with_labels.jsonl", {
            type: "application/x-ndjson",
          }),
        );
      },
      downloadKind: "corpus_with_labels.jsonl",
      savedLabel: t("editor.savedReload"),
    },
  ];
  if (envMode === "byok" && !readOnly) {
    fileTabs.push({
      label: t("editor.byokTab"),
      loadPath: "prompts/task_background.md",
      save: async () => {},
      savedLabel: "",
      byok: true,
    });
  }
  return fileTabs;
}

type ByokStatus = "idle" | "saving" | "saved" | "error";

interface ByokTabProps {
  sessionId: string;
  open: boolean;
  isActive: boolean;
}

function ByokTab({ sessionId, open, isActive }: ByokTabProps) {
  const { t } = useI18n();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [status, setStatus] = useState<ByokStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!open || !isActive) return;
    if (loadedRef.current) return;
    setLoading(true);
    setError(null);
    void getSessionEnv(sessionId)
      .then((env) => {
        setApiKey(env.overrides.OPENAI_API_KEY ?? "");
        setBaseUrl(env.overrides.OPENAI_BASE_URL ?? "");
        setModel(env.overrides.OPENAI_MODEL ?? "");
        loadedRef.current = true;
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : t("editor.byokLoadFailed"));
      })
      .finally(() => setLoading(false));
  }, [open, isActive, sessionId, t]);

  useEffect(() => {
    if (open) return;
    loadedRef.current = false;
    setStatus("idle");
    setError(null);
  }, [open]);

  if (!isActive) return null;

  const handleSave = async () => {
    setStatus("saving");
    setError(null);
    try {
      await saveSessionEnv(sessionId, {
        OPENAI_API_KEY: apiKey,
        OPENAI_BASE_URL: baseUrl,
        OPENAI_MODEL: model,
        OPENAI_MODEL_PRO: model,
      });
      setStatus("saved");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("editor.byokSaveFailed"));
      setStatus("error");
    }
  };

  const statusLabel = (() => {
    switch (status) {
      case "saving":
        return t("editor.byokSaving");
      case "saved":
        return t("editor.byokSaved");
      case "error":
        return t("editor.byokSaveFailed");
      default:
        return "";
    }
  })();

  const statusColor = (() => {
    switch (status) {
      case "saving":
        return terminalColors.gray;
      case "saved":
        return terminalColors.green;
      case "error":
        return terminalColors.red;
      default:
        return terminalColors.gray;
    }
  })();

  return (
    <Box>
      {error && (
        <Alert severity="warning" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Stack spacing={1.5}>
        <TextField
          fullWidth
          size="small"
          label="OPENAI_API_KEY"
          required
          type={showApiKey ? "text" : "password"}
          value={apiKey}
          disabled={loading}
          onChange={(event) => setApiKey(event.target.value)}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  edge="end"
                  onClick={() => setShowApiKey((prev) => !prev)}
                  sx={{ color: terminalColors.gray }}
                >
                  {showApiKey ? (
                    <VisibilityOffOutlinedIcon fontSize="small" />
                  ) : (
                    <VisibilityOutlinedIcon fontSize="small" />
                  )}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
        <TextField
          fullWidth
          size="small"
          label="OPENAI_BASE_URL"
          placeholder="https://api.deepseek.com/v1"
          value={baseUrl}
          disabled={loading}
          onChange={(event) => setBaseUrl(event.target.value)}
        />
        <TextField
          fullWidth
          size="small"
          label="OPENAI_MODEL"
          placeholder="deepseek-v4-flash"
          value={model}
          disabled={loading}
          onChange={(event) => setModel(event.target.value)}
        />
      </Stack>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1.5}
        sx={{ mt: 2 }}
      >
        <Button
          size="small"
          variant="outlined"
          disabled={loading || status === "saving" || !apiKey.trim()}
          onClick={() => void handleSave()}
          sx={{ borderColor: terminalColors.border, color: terminalColors.text }}
        >
          {t("editor.byokSave")}
        </Button>
        {status === "saving" && (
          <CircularProgress size={12} sx={{ color: statusColor }} />
        )}
        {statusLabel && (
          <Typography sx={{ fontSize: fontSizes.sm, color: statusColor }}>
            {statusLabel}
          </Typography>
        )}
      </Stack>
      <Typography
        sx={{
          mt: 1.5,
          fontSize: fontSizes.sm,
          color: terminalColors.gray,
          opacity: 0.7,
        }}
      >
        {t("editor.byokHint")}
      </Typography>
    </Box>
  );
}

export function WorkspaceEditor({ sessionId, envMode, open, onClose, readOnly }: WorkspaceEditorProps) {
  const { t } = useI18n();
  const tabs = buildTabs(t, envMode, readOnly);
  const [tabIndex, setTabIndex] = useState(0);
  const [tabStatus, setTabStatus] = useState<TabSaveStatus>({
    saveState: "idle",
    dirty: false,
  });

  const tabRefs = useRef<(EditableFileTabHandle | null)[]>([]);

  const handleClose = async () => {
    await tabRefs.current[tabIndex]?.flush();
    onClose();
  };

  const handleTabChange = async (_: unknown, next: number) => {
    if (next === tabIndex) return;
    await tabRefs.current[tabIndex]?.flush();
    setTabIndex(next);
    setTabStatus({ saveState: "idle", dirty: false });
  };

  const statusLabel = (() => {
    switch (tabStatus.saveState) {
      case "saving":
        return t("editor.saving");
      case "saved":
        return t("editor.saved");
      case "error":
        return t("editor.saveFailed");
      default:
        return tabStatus.dirty ? t("editor.unsaved") : t("editor.synced");
    }
  })();

  const statusColor = (() => {
    switch (tabStatus.saveState) {
      case "saving":
        return terminalColors.gray;
      case "saved":
        return terminalColors.green;
      case "error":
        return terminalColors.red;
      default:
        return tabStatus.dirty ? terminalColors.yellow : terminalColors.gray;
    }
  })();

  return (
    <Dialog open={open} onClose={() => void handleClose()} fullWidth maxWidth="md">
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          pb: 1,
        }}
      >
        <span>{t("editor.title")}</span>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.75,
            fontSize: fontSizes.sm,
            color: statusColor,
            fontWeight: 400,
          }}
        >
          {tabStatus.saveState === "saving" && (
            <CircularProgress size={12} sx={{ color: statusColor }} />
          )}
          <span>{readOnly ? t("editor.readOnly") : statusLabel}</span>
        </Box>
      </DialogTitle>
      <DialogContent>
        {!readOnly && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {t("editor.alert", { ms: AUTOSAVE_DELAY_MS })}
          </Alert>
        )}
        <Tabs
          value={tabIndex}
          onChange={(_, next) => void handleTabChange(_, next)}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          sx={{
            mb: 2,
            minHeight: 40,
            borderBottom: `1px solid ${terminalColors.border}`,
            "& .MuiTab-scrollButtons": { color: terminalColors.gray },
          }}
        >
          {tabs.map((tab) => (
            <Tab key={tab.label} label={tab.label} sx={{ fontSize: fontSizes.md, minHeight: 40 }} />
          ))}
        </Tabs>
        {tabs.map((tab, index) => {
          if (tab.byok) {
            return (
              <ByokTab
                key={tab.label}
                sessionId={sessionId}
                open={open}
                isActive={open && tabIndex === index}
              />
            );
          }
          return (
            <EditableFileTab
              key={tab.label}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              sessionId={sessionId}
              open={open}
              isActive={open && tabIndex === index}
              loadPath={tab.loadPath}
              save={tab.save}
              savedLabel={tab.savedLabel}
              downloadUrl={
                tab.downloadKind ? downloadFileUrl(sessionId, tab.downloadKind) : undefined
              }
              onStatusChange={tabIndex === index ? setTabStatus : () => {}}
              readOnly={readOnly}
            />
          );
        })}
        {!readOnly && (
          <Typography
            sx={{
              mt: 1,
              fontSize: fontSizes.sm,
              color: terminalColors.gray,
              opacity: 0.7,
            }}
          >
            {t("editor.hintSwitch")}
          </Typography>
        )}
      </DialogContent>
    </Dialog>
  );
}
