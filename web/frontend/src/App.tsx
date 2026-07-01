import { useCallback, useEffect, useState } from "react";
import { Box, Drawer, Snackbar, Alert, useMediaQuery, useTheme } from "@mui/material";
import { deleteSession, getSession } from "./api";
import { EntryScreen } from "./components/EntryScreen";
import { ShareScreen } from "./components/ShareScreen";
import { Sidebar, SidebarContent } from "./components/Sidebar";
import { Terminal } from "./components/Terminal";
import { useI18n } from "./i18n/LanguageContext";
import { usePresence } from "./hooks/usePresence";
import {
  listLocalSessions,
  registerLocalSession,
  removeLocalSession,
  touchLocalSession,
} from "./localSessions";
import { terminalColors } from "./theme";
import type { SessionSummary } from "./types";

export default function App() {
  const { t } = useI18n();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));

  const shareMatch = window.location.pathname.match(/^\/share\/(.+)$/);
  const shareSessionId = shareMatch?.[1] ?? null;

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [errorToast, setErrorToast] = useState<string | null>(null);
  const presence = usePresence();

  const refreshSessions = useCallback(async () => {
    const localRecords = listLocalSessions();
    if (localRecords.length === 0) {
      setSessions([]);
      setLoading(false);
      return;
    }

    const results = await Promise.all(
      localRecords.map(async (record) => {
        try {
          const detail = await getSession(record.id);
          return {
            id: detail.id,
            language: detail.language,
            created_at: record.last_opened,
            status_summary:
              typeof detail.status === "object" &&
              detail.status &&
              "coded_count" in detail.status
                ? t("app.statusSummary", {
                    texts: Number(detail.status.texts_total ?? 0),
                    coded: Number(detail.status.coded_count ?? 0),
                    queue: Number(detail.status.queue_remaining ?? 0),
                    dimensions: Number(detail.status.dimensions_count ?? 0),
                  })
                : record.id,
            workspace_root: String(detail.meta?.workspace_resolved ?? ""),
            env_mode: detail.env_mode,
            prompt_set: detail.prompt_set,
          } satisfies SessionSummary;
        } catch {
          removeLocalSession(record.id);
          return null;
        }
      }),
    );

    setSessions(results.filter((item): item is SessionSummary => item !== null));
    setLoading(false);
  }, [t]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const handleOpenSession = async (
    sessionId: string,
    meta?: { env_mode: SessionSummary["env_mode"]; prompt_set: SessionSummary["prompt_set"]; language: string },
  ) => {
    try {
      const detail = await getSession(sessionId);
      registerLocalSession({
        id: detail.id,
        env_mode: detail.env_mode,
        prompt_set: detail.prompt_set,
        language: detail.language,
      });
    } catch {
      if (meta) {
        registerLocalSession({
          id: sessionId,
          env_mode: meta.env_mode,
          prompt_set: meta.prompt_set,
          language: meta.language,
        });
      }
    }
    touchLocalSession(sessionId);
    setActiveSessionId(sessionId);
    setDrawerOpen(false);
    await refreshSessions();
  };

  const handleDelete = async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      removeLocalSession(sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
      }
      await refreshSessions();
    } catch (err) {
      setErrorToast(err instanceof Error ? err.message : t("app.deleteFailed"));
    }
  };

  const activeSession = sessions.find((item) => item.id === activeSessionId);

  const sidebarProps = {
    sessions,
    activeSessionId,
    onSelect: (sessionId: string) => void handleOpenSession(sessionId),
    onDelete: handleDelete,
    onRefresh: refreshSessions,
    onHome: () => {
      setActiveSessionId(null);
      setDrawerOpen(false);
    },
  };

  if (shareSessionId) {
    return (
      <Box sx={{ minHeight: "100vh", bgcolor: terminalColors.bg }}>
        <ShareScreen sessionId={shareSessionId} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: terminalColors.bg }}>
      {activeSessionId && isDesktop && <Sidebar {...sidebarProps} />}

      {activeSessionId && !isDesktop && (
        <Drawer
          anchor="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          PaperProps={{
            sx: {
              width: 280,
              bgcolor: terminalColors.panel,
              borderRight: `1px solid ${terminalColors.border}`,
            },
          }}
        >
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              height: "100%",
            }}
          >
            <SidebarContent {...sidebarProps} />
          </Box>
        </Drawer>
      )}

      <Box sx={{ flex: 1, minWidth: 0 }}>
        {activeSessionId ? (
          <Terminal
            key={activeSessionId}
            sessionId={activeSessionId}
            envMode={activeSession?.env_mode ?? "env"}
            promptSet={activeSession?.prompt_set ?? "baseline"}
            presence={presence}
            onExit={() => setActiveSessionId(null)}
            onOpenSidebar={!isDesktop ? () => setDrawerOpen(true) : undefined}
          />
        ) : (
          <EntryScreen
            loading={loading}
            recentSessions={sessions}
            presence={presence}
            onOpen={(sessionId) => void handleOpenSession(sessionId)}
            onCreated={(session) =>
              void handleOpenSession(session.id, {
                env_mode: session.env_mode,
                prompt_set: session.prompt_set,
                language: session.language,
              })
            }
          />
        )}
      </Box>

      <Snackbar
        open={errorToast !== null}
        autoHideDuration={5000}
        onClose={() => setErrorToast(null)}
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert
          severity="error"
          variant="filled"
          onClose={() => setErrorToast(null)}
          sx={{ width: "100%" }}
        >
          {errorToast}
        </Alert>
      </Snackbar>
    </Box>
  );
}
