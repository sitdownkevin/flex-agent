import { useEffect, useMemo, useState, type MouseEvent } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Divider,
  FormControl,
  FormControlLabel,
  FormLabel,
  IconButton,
  InputAdornment,
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
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import GitHubIcon from "@mui/icons-material/GitHub";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import { createSession, getSession } from "../api";
import { useI18n } from "../i18n/LanguageContext";
import type { UiLang } from "../i18n";
import { cardSx, fontSizes, sectionAccentSx, terminalColors } from "../theme";
import type { EnvMode, PresenceStats, PromptSet, SessionDetail, SessionSummary } from "../types";

const GITHUB_URL = "https://github.com/TJ-IS/flex-agent";

interface EntryScreenProps {
  loading: boolean;
  recentSessions: SessionSummary[];
  presence: PresenceStats;
  onOpen: (sessionId: string) => void;
  onCreated: (session: SessionDetail) => void;
}

const ALL_PROMPT_OPTIONS: { value: PromptSet; lang: UiLang; hintKey: string }[] = [
  { value: "baseline", lang: "zh", hintKey: "entry.hints.baseline" },
  { value: "baseline_oneshot", lang: "zh", hintKey: "entry.hints.baseline_oneshot" },
  { value: "baseline_fewshot", lang: "zh", hintKey: "entry.hints.baseline_fewshot" },
  { value: "baseline_en", lang: "en", hintKey: "entry.hints.baseline_en" },
  { value: "baseline_oneshot_en", lang: "en", hintKey: "entry.hints.baseline_oneshot_en" },
  { value: "baseline_fewshot_en", lang: "en", hintKey: "entry.hints.baseline_fewshot_en" },
];

const sectionTitleSx = {
  fontFamily: '"Instrument Serif", serif',
  fontWeight: 400,
  fontSize: fontSizes.lg,
  ...sectionAccentSx,
};

export function EntryScreen({
  loading,
  recentSessions,
  presence,
  onOpen,
  onCreated,
}: EntryScreenProps) {
  const { lang, setLang, t } = useI18n();

  const [openId, setOpenId] = useState("");
  const [openError, setOpenError] = useState<string | null>(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [recentCollapsed, setRecentCollapsed] = useState(true);

  const [mode, setMode] = useState<EnvMode>("env");
  const promptOptions = useMemo(
    () => ALL_PROMPT_OPTIONS.filter((option) => option.lang === lang),
    [lang],
  );
  const [promptSet, setPromptSet] = useState<PromptSet>("baseline");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createLoading, setCreateLoading] = useState(false);

  useEffect(() => {
    setPromptSet((current) => {
      if (promptOptions.some((option) => option.value === current)) return current;
      return promptOptions[0]?.value ?? "baseline";
    });
  }, [promptOptions]);

  const handleOpen = async (sessionId?: string) => {
    const trimmed = (sessionId ?? openId).trim();
    if (!trimmed) {
      setOpenError(t("entry.openErrorEmpty"));
      return;
    }
    setOpenLoading(true);
    setOpenError(null);
    try {
      await getSession(trimmed);
      onOpen(trimmed);
    } catch (error) {
      setOpenError(error instanceof Error ? error.message : t("entry.openErrorFailed"));
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
        language: lang,
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
      setCreateError(error instanceof Error ? error.message : t("entry.createError"));
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
              fontFamily: '"Instrument Serif", serif',
              fontWeight: 400,
              letterSpacing: 0,
              pb: 1.5,
              background: `linear-gradient(90deg, transparent, ${terminalColors.cyan}, transparent)`,
              backgroundSize: "100% 1px",
              backgroundRepeat: "no-repeat",
              backgroundPosition: "bottom",
            }}
          >
            {t("entry.brandTitle")}
          </Typography>
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="center"
            gap={1.5}
            sx={{ pb: 0.5 }}
          >
            <Tooltip title={t("entry.githubTooltip")} arrow>
              <IconButton
                component="a"
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                  color: terminalColors.gray,
                  "&:hover": { color: terminalColors.text },
                }}
              >
                <GitHubIcon />
              </IconButton>
            </Tooltip>
            <Chip
              size="small"
              variant="outlined"
              label={t("entry.presenceOnline", {
                sessions: presence.online_sessions,
              })}
              sx={{
                color: terminalColors.green,
                borderColor: "rgba(63, 185, 80, 0.45)",
                bgcolor: "rgba(63, 185, 80, 0.06)",
                fontSize: fontSizes.sm,
                height: 24,
                "& .MuiChip-label": { px: 1 },
              }}
            />
            <ToggleButtonGroup
              exclusive
              size="small"
              value={lang}
              onChange={(_event, next: UiLang | null) => {
                if (next !== null) setLang(next);
              }}
              sx={{
                borderRadius: 999,
                border: `1px solid ${terminalColors.border}`,
                bgcolor: "rgba(255,255,255,0.03)",
                overflow: "hidden",
                "& .MuiToggleButton-root": {
                  color: terminalColors.gray,
                  border: "none",
                  borderRight: `1px solid ${terminalColors.border}`,
                  borderRadius: 0,
                  px: 1.4,
                  py: 0.25,
                  fontSize: fontSizes.sm,
                  lineHeight: 1.4,
                  height: 24,
                  minWidth: 38,
                  transition: "all 160ms ease",
                  "&:last-child": { borderRight: "none" },
                  "&.Mui-selected": {
                    color: terminalColors.cyan,
                    bgcolor: "rgba(57, 197, 207, 0.16)",
                    "&:hover": { bgcolor: "rgba(57, 197, 207, 0.24)" },
                  },
                  "&:not(.Mui-selected):hover": {
                    color: terminalColors.text,
                    bgcolor: "rgba(255, 255, 255, 0.05)",
                  },
                },
              }}
            >
              <ToggleButton value="zh">中</ToggleButton>
              <ToggleButton value="en">EN</ToggleButton>
            </ToggleButtonGroup>
          </Stack>
        </Box>

        <Card sx={cardSx}>
          <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
            <Typography sx={{ ...sectionTitleSx, mb: 2 }}>
              {t("entry.openTitle")}
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
                {t("entry.openButton")}
              </Button>
            </Stack>
            {openError && (
              <Typography sx={{ color: terminalColors.yellow, mt: 1.5, fontSize: fontSizes.sm }}>
                {openError}
              </Typography>
            )}
          </CardContent>
        </Card>

        <Divider
          sx={{
            borderColor: terminalColors.border,
            fontSize: fontSizes.sm,
            color: terminalColors.gray,
            "&::before, &::after": {
              borderColor: terminalColors.border,
            },
          }}
        >
          {t("entry.or")}
        </Divider>

        <Card sx={cardSx}>
          <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
            <Typography sx={{ ...sectionTitleSx, mb: 2 }}>
              {t("entry.createTitle")}
            </Typography>

            <FormControl fullWidth sx={{ mb: 2.5 }}>
              <FormLabel sx={{ color: terminalColors.gray, mb: 1, fontSize: fontSizes.md }}>
                {t("entry.modeLabel")}
              </FormLabel>
              <RadioGroup
                row
                value={mode}
                onChange={(event) => setMode(event.target.value as EnvMode)}
              >
                <FormControlLabel
                  value="env"
                  control={<Radio size="small" />}
                  label={t("entry.modeEnv")}
                />
                <FormControlLabel
                  value="byok"
                  control={<Radio size="small" />}
                  label={t("entry.modeByok")}
                />
              </RadioGroup>
            </FormControl>

            {mode === "byok" && (
              <Stack spacing={1.5} sx={{ mb: 2.5 }}>
                <TextField
                  fullWidth
                  size="small"
                  label="OPENAI_API_KEY"
                  required
                  type={showApiKey ? "text" : "password"}
                  value={apiKey}
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
                  onChange={(event) => setBaseUrl(event.target.value)}
                />
                <TextField
                  fullWidth
                  size="small"
                  label="OPENAI_MODEL"
                  placeholder="deepseek-v4-flash"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                />
              </Stack>
            )}

            <FormControl fullWidth size="small" sx={{ mb: 1 }}>
              <FormLabel sx={{ color: terminalColors.gray, mb: 1, fontSize: fontSizes.md }}>
                {t("entry.promptSetLabel")}
              </FormLabel>
              <Select
                value={promptSet}
                onChange={(event) => setPromptSet(event.target.value as PromptSet)}
              >
                {promptOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.value}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Typography sx={{ color: terminalColors.gray, fontSize: fontSizes.sm, mb: 2.5 }}>
              {t(ALL_PROMPT_OPTIONS.find((item) => item.value === promptSet)?.hintKey ?? "")}
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
              {t("entry.createButton")}
            </Button>
            {createError && (
              <Typography sx={{ color: terminalColors.yellow, mt: 1.5, fontSize: fontSizes.sm }}>
                {createError}
              </Typography>
            )}
          </CardContent>
        </Card>

        {!loading && recentSessions.length > 0 && (
          <Card sx={cardSx}>
            <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
              <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                sx={{ mb: recentCollapsed ? 0 : 1 }}
              >
                <Typography sx={sectionTitleSx}>{t("entry.recentTitle")}</Typography>
                <Tooltip
                  title={t(recentCollapsed ? "entry.recentExpandTooltip" : "entry.recentCollapseTooltip")}
                  arrow
                >
                  <IconButton
                    size="small"
                    onClick={() => setRecentCollapsed((prev) => !prev)}
                    sx={{ color: terminalColors.gray, "&:hover": { color: terminalColors.text } }}
                  >
                    {recentCollapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
                  </IconButton>
                </Tooltip>
              </Stack>
              <Collapse in={!recentCollapsed}>
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
                        primaryTypographyProps={{ fontSize: fontSizes.md, fontWeight: 600 }}
                        secondaryTypographyProps={{ fontSize: fontSizes.sm, color: terminalColors.gray }}
                      />
                      <Tooltip title={t("entry.copyTooltip")}>
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
                        <Chip label={session.env_mode} size="small" sx={{ height: 20, fontSize: fontSizes.xs }} />
                        <Chip label={session.prompt_set} size="small" sx={{ height: 20, fontSize: fontSizes.xs }} />
                      </Stack>
                    </ListItemButton>
                  ))}
                </List>
              </Collapse>
            </CardContent>
          </Card>
        )}
      </Stack>
    </Box>
  );
}
