import { useState } from "react";
import {
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import GitHubIcon from "@mui/icons-material/GitHub";
import { useI18n } from "../i18n/LanguageContext";
import { fontSizes, terminalColors } from "../theme";
import type { SessionSummary } from "../types";
import { ConfirmDialog } from "./ConfirmDialog";

const GITHUB_URL = "https://github.com/TJ-IS/flex-agent";

export interface SidebarContentProps {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onRefresh: () => void;
  onHome: () => void;
}

export function SidebarContent({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onRefresh: _onRefresh,
  onHome,
}: SidebarContentProps) {
  const { t } = useI18n();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  return (
    <>
      <Box sx={{ p: 2 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography
            variant="h6"
            sx={{ fontFamily: '"Instrument Serif", serif', fontWeight: 400, mb: 0.5 }}
          >
            CODE
          </Typography>
          <Tooltip title={t("sidebar.githubTooltip")} arrow>
            <IconButton
              size="small"
              component="a"
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ color: terminalColors.gray, "&:hover": { color: terminalColors.text } }}
            >
              <GitHubIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Stack>
        <Typography variant="caption" sx={{ color: terminalColors.gray, display: "block" }}>
          {t("entry.subtitle")}
        </Typography>
        <Button size="small" variant="text" sx={{ mt: 1, px: 0 }} onClick={onHome}>
          {t("sidebar.home")}
        </Button>
      </Box>

      <Divider sx={{ borderColor: terminalColors.border }} />

      <Box sx={{ flex: 1, overflow: "auto" }}>
        <Typography
          variant="caption"
          sx={{ color: terminalColors.gray, px: 2, py: 1, display: "block" }}
        >
          {t("sidebar.recentTitle")}
        </Typography>
        <List dense disablePadding>
          {sessions.length === 0 ? (
            <Typography sx={{ color: terminalColors.gray, px: 2, py: 1, fontSize: fontSizes.sm }}>
              {t("sidebar.empty")}
            </Typography>
          ) : (
            sessions.map((session) => (
              <ListItemButton
                key={session.id}
                selected={session.id === activeSessionId}
                onClick={() => onSelect(session.id)}
                sx={{
                  borderBottom: `1px solid ${terminalColors.border}`,
                  "&.Mui-selected": {
                    bgcolor: "rgba(57, 197, 207, 0.12)",
                  },
                }}
              >
                <ListItemText
                  primary={session.id}
                  secondary={
                    <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                      <Typography variant="caption" sx={{ color: terminalColors.gray }}>
                        {session.status_summary}
                      </Typography>
                      <Stack direction="row" spacing={0.5} useFlexGap flexWrap="wrap">
                        <Chip
                          size="small"
                          label={session.env_mode}
                          sx={{ height: 18, fontSize: fontSizes.xs }}
                        />
                        <Chip
                          size="small"
                          label={session.prompt_set}
                          sx={{ height: 18, fontSize: fontSizes.xs }}
                        />
                      </Stack>
                    </Stack>
                  }
                  primaryTypographyProps={{
                    fontSize: fontSizes.sm,
                    noWrap: true,
                  }}
                  secondaryTypographyProps={{ component: "div" }}
                />
              </ListItemButton>
            ))
          )}
        </List>
      </Box>

      {activeSessionId && (
        <>
          <Divider sx={{ borderColor: terminalColors.border }} />
          <Box sx={{ p: 1.5 }}>
            <Typography variant="caption" sx={{ color: terminalColors.gray, mb: 1, display: "block" }}>
              Session: {activeSessionId}
            </Typography>
            <Stack spacing={0.75}>
              <Button
                size="small"
                color="error"
                variant="text"
                fullWidth
                onClick={() => setConfirmDeleteId(activeSessionId)}
              >
                {t("sidebar.deleteSession")}
              </Button>
            </Stack>
          </Box>
        </>
      )}

      <ConfirmDialog
        open={confirmDeleteId !== null}
        title={t("sidebar.confirmTitle")}
        message={t("sidebar.confirmMessage", { id: confirmDeleteId ?? "" })}
        confirmLabel={t("sidebar.confirmLabel")}
        confirmColor="error"
        onConfirm={() => {
          if (confirmDeleteId) onDelete(confirmDeleteId);
        }}
        onClose={() => setConfirmDeleteId(null)}
      />
    </>
  );
}

export function Sidebar(props: SidebarContentProps) {
  return (
    <Box
      sx={{
        width: 280,
        minWidth: 280,
        borderRight: `1px solid ${terminalColors.border}`,
        bgcolor: terminalColors.panel,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      <SidebarContent {...props} />
    </Box>
  );
}
