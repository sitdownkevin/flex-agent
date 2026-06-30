import { useEffect, useState, type MouseEvent } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Divider,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { createSession, getSession, languageForPromptSet } from "../api";
import { cardSx, sectionAccentSx, terminalColors } from "../theme";
import type { EnvMode, PromptSet, SessionDetail, SessionSummary } from "../types";

interface EntryScreenProps {
  loading: boolean;
  recentSessions: SessionSummary[];
  onOpen: (sessionId: string) => void;
  onCreated: (session: SessionDetail) => void;
}

const PROMPT_OPTIONS: { value: PromptSet; label: string; hint: string }[] = [
  { value: "baseline", label: "baseline", hint: "Chinese baseline prompt set" },
  { value: "baseline_en", label: "baseline_en", hint: "English baseline prompt set" },
  { value: "baseline_oneshot", label: "baseline_oneshot", hint: "Chinese baseline one-shot variant" },
  { value: "baseline_fewshot", label: "baseline_fewshot", hint: "Chinese baseline few-shot variant" },
];

const sectionTitleSx = {
  fontWeight: 700,
  ...sectionAccentSx,
};

export function EntryScreen({
  loading,
  recentSessions,
  onOpen,
  onCreated,
}: EntryScreenProps) {
  const [openId, setOpenId] = useState("");
  const [openError, setOpenError] = useState<string | null>(null);
  const [openLoading, setOpenLoading] = useState(false);

  const [mode, setMode] = useState<EnvMode>("env");
  const [promptSet, setPromptSet] = useState<PromptSet>("baseline");
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createLoading, setCreateLoading] = useState(false);

  useEffect(() => {
    setLanguage(languageForPromptSet(promptSet));
  }, [promptSet]);

  const handleOpen = async (sessionId?: string) => {
    const trimmed = (sessionId ?? openId).trim();
    if (!trimmed) {
      setOpenError("请输入 session_id");
      return;
    }
    setOpenLoading(true);
    setOpenError(null);
    try {
      await getSession(trimmed);
      onOpen(trimmed);
    } catch (error) {
      setOpenError(error instanceof Error ? error.message : "打开失败，请确认 session_id 是否正确");
    } finally {
      setOpenLoading(false);
    }
  };

  const handleCopySessionId = async (sessionId: string, event: MouseEvent) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(sessionId);
    } catch {
      // ignore clipboard errors
    }
  };

  const handleCreate = async () => {
    setCreateLoading(true);
    setCreateError(null);
    try {
      const session = await createSession({
        language,
        prompt_set: promptSet,
        mode,
        overrides:
          mode === "byok"
            ? {
                OPENAI_API_KEY: apiKey.trim(),
                OPENAI_BASE_URL: baseUrl.trim(),
                OPENAI_MODEL: model.trim(),
                OPENAI_MODEL_PRO: model.trim(),
              }
            : {},
      });
      onCreated(session);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "创建失败");
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        px: { xs: 2, sm: 3 },
        py: { xs: 3, sm: 5 },
      }}
    >
      <Stack spacing={3} sx={{ width: "100%", maxWidth: 720 }}>
        <Box sx={{ textAlign: "center", pt: 1, pb: 0.5 }}>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              letterSpacing: "-0.02em",
              pb: 1.5,
              background: `linear-gradient(90deg, transparent, ${terminalColors.cyan}, transparent)`,
              backgroundSize: "100% 1px",
              backgroundRepeat: "no-repeat",
              backgroundPosition: "bottom",
            }}
          >
            CODE: COnstruct Development Engine
          </Typography>
          <Typography sx={{ color: terminalColors.gray, mt: 1 }}>
            输入 session_id 恢复 workspace
            <br />
            或创建新的 workspace
          </Typography>
        </Box>

        {!loading && recentSessions.length > 0 && (
          <Card sx={cardSx}>
            <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
              <Typography variant="subtitle2" sx={{ ...sectionTitleSx, mb: 1 }}>
                本机最近使用
              </Typography>
              <List dense disablePadding>
                {recentSessions.map((session) => (
                  <ListItemButton
                    key={session.id}
                    onClick={() => void handleOpen(session.id)}
                    disabled={openLoading}
                    sx={{
                      border: `1px solid ${terminalColors.border}`,
                      borderRadius: 1,
                      mb: 0.75,
                      px: 1.5,
                      "&:hover": {
                        bgcolor: "rgba(57, 197, 207, 0.06)",
                        "& .copy-btn": { opacity: 1 },
                      },
                    }}
                  >
                    <ListItemText
                      primary={session.id}
                      secondary={session.status_summary}
                      primaryTypographyProps={{ fontSize: "0.82rem", fontWeight: 600 }}
                      secondaryTypographyProps={{ fontSize: "0.72rem", color: terminalColors.gray }}
                    />
                    <Tooltip title="复制 session_id">
                      <IconButton
                        className="copy-btn"
                        size="small"
                        onClick={(event) => void handleCopySessionId(session.id, event)}
                        sx={{
                          mr: 0.5,
                          opacity: { xs: 1, sm: 0 },
                          transition: "opacity 200ms ease",
                        }}
                      >
                        <ContentCopyIcon sx={{ fontSize: "0.9rem" }} />
                      </IconButton>
                    </Tooltip>
                    <Stack direction="row" spacing={0.5}>
                      <Chip label={session.env_mode} size="small" sx={{ height: 20, fontSize: "0.65rem" }} />
                      <Chip label={session.prompt_set} size="small" sx={{ height: 20, fontSize: "0.65rem" }} />
                    </Stack>
                  </ListItemButton>
                ))}
              </List>
            </CardContent>
          </Card>
        )}

        <Card sx={cardSx}>
          <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
            <Typography variant="subtitle1" sx={{ ...sectionTitleSx, mb: 2 }}>
              打开已有 workspace
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              <TextField
                fullWidth
                size="small"
                label="session_id"
                placeholder="sess_20260630_173257_405864"
                value={openId}
                onChange={(event) => setOpenId(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleOpen();
                }}
              />
              <Button
                variant="contained"
                disabled={openLoading}
                onClick={() => void handleOpen()}
                sx={{ minWidth: { sm: 96 }, alignSelf: { sm: "flex-end" }, height: 40 }}
              >
                打开
              </Button>
            </Stack>
            {openError && (
              <Typography sx={{ color: terminalColors.yellow, mt: 1.5, fontSize: "0.85rem" }}>
                {openError}
              </Typography>
            )}
          </CardContent>
        </Card>

        <Divider
          sx={{
            borderColor: terminalColors.border,
            fontSize: "0.75rem",
            color: terminalColors.gray,
            "&::before, &::after": {
              borderColor: terminalColors.border,
            },
          }}
        >
          或
        </Divider>

        <Card sx={cardSx}>
          <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
            <Typography variant="subtitle1" sx={{ ...sectionTitleSx, mb: 2 }}>
              新建 workspace
            </Typography>

            <FormControl fullWidth sx={{ mb: 2.5 }}>
              <FormLabel sx={{ color: terminalColors.gray, mb: 1, fontSize: "0.85rem" }}>
                模式
              </FormLabel>
              <RadioGroup
                row
                value={mode}
                onChange={(event) => setMode(event.target.value as EnvMode)}
              >
                <FormControlLabel
                  value="env"
                  control={<Radio size="small" />}
                  label="Default Provider"
                />
                <FormControlLabel
                  value="byok"
                  control={<Radio size="small" />}
                  label="BYOK (Bring Your Own Key)"
                />
              </RadioGroup>
            </FormControl>

            {mode === "byok" && (
              <Stack spacing={1.5} sx={{ mb: 2.5 }}>
                <Stack direction="row" spacing={1} alignItems="flex-end">
                  <TextField
                    size="small"
                    label="OPENAI_API_KEY"
                    required
                    fullWidth
                    type={showApiKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                  />
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => setShowApiKey((prev) => !prev)}
                    sx={{ minWidth: 72, height: 40, borderColor: terminalColors.border }}
                  >
                    {showApiKey ? "隐藏" : "显示"}
                  </Button>
                </Stack>
                <Grid container spacing={1.5}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      size="small"
                      label="OPENAI_BASE_URL"
                      placeholder="https://api.deepseek.com/v1"
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      size="small"
                      label="OPENAI_MODEL"
                      placeholder="deepseek-v4-flash"
                      value={model}
                      onChange={(event) => setModel(event.target.value)}
                    />
                  </Grid>
                </Grid>
              </Stack>
            )}

            <Grid container spacing={1.5} sx={{ mb: 1 }}>
              <Grid item xs={12} sm={7}>
                <FormControl fullWidth size="small">
                  <FormLabel sx={{ color: terminalColors.gray, mb: 1, fontSize: "0.85rem" }}>
                    Prompt 集
                  </FormLabel>
                  <Select
                    value={promptSet}
                    onChange={(event) => setPromptSet(event.target.value as PromptSet)}
                  >
                    {PROMPT_OPTIONS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={5}>
                <FormControl fullWidth size="small">
                  <FormLabel sx={{ color: terminalColors.gray, mb: 1, fontSize: "0.85rem" }}>
                    语言
                  </FormLabel>
                  <Select
                    value={language}
                    onChange={(event) => setLanguage(event.target.value as "zh" | "en")}
                  >
                    <MenuItem value="zh">zh</MenuItem>
                    <MenuItem value="en">en</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>

            <Typography sx={{ color: terminalColors.gray, fontSize: "0.8rem", mb: 2.5 }}>
              {PROMPT_OPTIONS.find((item) => item.value === promptSet)?.hint}
            </Typography>

            <Button
              variant="contained"
              fullWidth
              size="large"
              disabled={createLoading}
              onClick={() => void handleCreate()}
              sx={{
                height: 44,
                transition: "transform 100ms ease",
                "&:active": { transform: "scale(0.98)" },
              }}
            >
              创建并进入
            </Button>
            {createError && (
              <Typography sx={{ color: terminalColors.yellow, mt: 1.5, fontSize: "0.85rem" }}>
                {createError}
              </Typography>
            )}
          </CardContent>
        </Card>
      </Stack>
    </Box>
  );
}
