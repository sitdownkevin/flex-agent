import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { getTaskBackground, saveTaskBackground } from "../api";
import { monoFont, terminalColors } from "../theme";

interface TaskBackgroundEditorProps {
  sessionId: string;
  open: boolean;
  onClose: () => void;
}

export function TaskBackgroundEditor({
  sessionId,
  open,
  onClose,
}: TaskBackgroundEditorProps) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    void getTaskBackground(sessionId)
      .then((text) => setContent(text))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "加载失败");
      })
      .finally(() => setLoading(false));
  }, [open, sessionId]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveTaskBackground(sessionId, content);
      alert("已保存 task_background.md，agent 已重载。");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Edit task_background.md</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          After saving, the agent will be reloaded, and the new prompt will take effect immediately; the coding status of the workspace will be preserved, and the conversation memory will be reset.
        </Alert>
        {error && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <TextField
          fullWidth
          multiline
          minRows={12}
          maxRows={24}
          value={content}
          disabled={loading || saving}
          onChange={(event) => setContent(event.target.value)}
          placeholder={loading ? "Loading…" : ""}
          InputProps={{
            sx: {
              fontFamily: monoFont,
              fontSize: "0.85rem",
              color: terminalColors.text,
            },
          }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={() => void handleSave()} disabled={loading || saving}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
