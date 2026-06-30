import { useCallback, useEffect, useState } from "react";
import { Box, Drawer, useMediaQuery, useTheme } from "@mui/material";
import { deleteSession, getSession } from "./api";
import { EntryScreen } from "./components/EntryScreen";
import { Sidebar, SidebarContent } from "./components/Sidebar";
import { Terminal } from "./components/Terminal";
import {
  listLocalSessions,
  registerLocalSession,
  removeLocalSession,
  touchLocalSession,
} from "./localSessions";
import { terminalColors } from "./theme";
import type { SessionSummary } from "./types";

export default function App() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);

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
                ? `texts=${detail.status.texts_total ?? 0} · coded=${detail.status.coded_count ?? 0} · queue=${detail.status.queue_remaining ?? 0} · dimensions=${detail.status.dimensions_count ?? 0}`
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
  }, []);

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
      alert(err instanceof Error ? err.message : "删除 session 失败");
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
            onExit={() => setActiveSessionId(null)}
            onOpenSidebar={!isDesktop ? () => setDrawerOpen(true) : undefined}
          />
        ) : (
          <EntryScreen
            loading={loading}
            recentSessions={sessions}
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
    </Box>
  );
}
