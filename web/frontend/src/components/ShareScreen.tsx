import { useEffect, useState } from "react";
import { Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import { getSession } from "../api";
import { useI18n } from "../i18n/LanguageContext";
import { terminalColors } from "../theme";
import type { PresenceStats, SessionDetail } from "../types";
import { Terminal } from "./Terminal";

interface ShareScreenProps {
  sessionId: string;
}

const STATIC_PRESENCE: PresenceStats = {
  online_sessions: 0,
  online_connections: 0,
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; detail: SessionDetail };

export function ShareScreen({ sessionId }: ShareScreenProps) {
  const { t } = useI18n();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    void getSession(sessionId)
      .then((detail) => {
        if (!cancelled) setState({ status: "ready", detail });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : t("share.notFound");
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, t]);

  if (state.status === "loading") {
    return (
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: terminalColors.bg,
        }}
      >
        <Stack spacing={2} alignItems="center">
          <CircularProgress size={28} sx={{ color: terminalColors.cyan }} />
          <Typography sx={{ color: terminalColors.gray, fontSize: "0.85rem" }}>
            {t("share.loading")}
          </Typography>
        </Stack>
      </Box>
    );
  }

  if (state.status === "error") {
    return (
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: terminalColors.bg,
          px: 2,
        }}
      >
        <Stack spacing={2} alignItems="center" sx={{ textAlign: "center" }}>
          <Typography
            sx={{
              color: terminalColors.yellow,
              fontFamily: '"Instrument Serif", serif',
              fontSize: "1.5rem",
            }}
          >
            {t("share.notFound")}
          </Typography>
          <Typography sx={{ color: terminalColors.gray, fontSize: "0.85rem" }}>
            {state.message}
          </Typography>
          <Button
            variant="outlined"
            href="/"
            sx={{ borderColor: terminalColors.border, color: terminalColors.text }}
          >
            {t("share.backHome")}
          </Button>
        </Stack>
      </Box>
    );
  }

  const { detail } = state;
  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: terminalColors.bg }}>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Terminal
          key={detail.id}
          sessionId={detail.id}
          envMode={detail.env_mode}
          promptSet={detail.prompt_set}
          presence={STATIC_PRESENCE}
          onExit={() => {}}
          shareMode
        />
      </Box>
    </Box>
  );
}
