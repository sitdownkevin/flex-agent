import { useRef } from "react";
import {
  Box,
  Button,
  Chip,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import { terminalColors } from "../theme";
import type { SessionSummary } from "../types";
import { downloadFileUrl, uploadFile } from "../api";

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
  onRefresh,
  onHome,
}: SidebarContentProps) {
  const corpusInputRef = useRef<HTMLInputElement>(null);
  const labelsInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (
    kind: "corpus.jsonl" | "corpus_with_labels.jsonl",
    file: File | undefined,
  ) => {
    if (!activeSessionId || !file) return;
    try {
      await uploadFile(activeSessionId, kind, file);
      onRefresh();
      alert("上传成功");
    } catch (error) {
      alert(error instanceof Error ? error.message : "上传失败");
    }
  };

  return (
    <>
      <Box sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
          CODE
        </Typography>
        <Typography variant="caption" sx={{ color: terminalColors.gray, display: "block" }}>
          COnstruct Development Engine
        </Typography>
        <Button size="small" variant="text" sx={{ mt: 1, px: 0 }} onClick={onHome}>
          首页
        </Button>
      </Box>

      <Divider sx={{ borderColor: terminalColors.border }} />

      <Box sx={{ flex: 1, overflow: "auto" }}>
        <Typography
          variant="caption"
          sx={{ color: terminalColors.gray, px: 2, py: 1, display: "block" }}
        >
          本机最近使用
        </Typography>
        <List dense disablePadding>
          {sessions.length === 0 ? (
            <Typography sx={{ color: terminalColors.gray, px: 2, py: 1, fontSize: "0.75rem" }}>
              暂无记录
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
                          sx={{ height: 18, fontSize: "0.65rem" }}
                        />
                        <Chip
                          size="small"
                          label={session.prompt_set}
                          sx={{ height: 18, fontSize: "0.65rem" }}
                        />
                      </Stack>
                    </Stack>
                  }
                  primaryTypographyProps={{
                    fontSize: "0.75rem",
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
                variant="outlined"
                fullWidth
                href={downloadFileUrl(activeSessionId, "corpus.jsonl")}
                download
                sx={{ borderColor: terminalColors.border }}
              >
                下载 corpus 模板
              </Button>
              <Button
                size="small"
                variant="outlined"
                fullWidth
                href={downloadFileUrl(activeSessionId, "corpus_with_labels.jsonl")}
                download
                sx={{ borderColor: terminalColors.border }}
              >
                下载 labels 模板
              </Button>
              <Button
                size="small"
                variant="text"
                fullWidth
                onClick={() => corpusInputRef.current?.click()}
              >
                上传 corpus
              </Button>
              <Button
                size="small"
                variant="text"
                fullWidth
                onClick={() => labelsInputRef.current?.click()}
              >
                上传 labels
              </Button>
              <Button
                size="small"
                color="error"
                variant="text"
                fullWidth
                onClick={() => {
                  if (confirm(`删除 session ${activeSessionId}?`)) {
                    onDelete(activeSessionId);
                  }
                }}
              >
                删除 session
              </Button>
            </Stack>
            <input
              ref={corpusInputRef}
              type="file"
              accept=".jsonl,application/json"
              hidden
              onChange={(event) => {
                void handleUpload("corpus.jsonl", event.target.files?.[0]);
                event.target.value = "";
              }}
            />
            <input
              ref={labelsInputRef}
              type="file"
              accept=".jsonl,application/json"
              hidden
              onChange={(event) => {
                void handleUpload("corpus_with_labels.jsonl", event.target.files?.[0]);
                event.target.value = "";
              }}
            />
          </Box>
        </>
      )}
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
