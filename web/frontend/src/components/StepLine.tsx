import { Box, Typography } from "@mui/material";
import { terminalColors } from "../theme";
import type { StepRecord } from "../types";

const ICONS: Record<StepRecord["status"], string> = {
  running: "◐",
  done: "✓",
  error: "✗",
};

const COLORS: Record<StepRecord["status"], string> = {
  running: terminalColors.yellow,
  done: terminalColors.green,
  error: terminalColors.red,
};

interface StepLineProps {
  step: StepRecord;
}

export function StepLine({ step }: StepLineProps) {
  const summary = step.summary ? ` ${step.summary}` : "";
  const preview = step.result_preview.trim();
  const showPreview =
    preview && (step.status === "done" || step.status === "error");

  return (
    <Box sx={{ mb: 0.5 }}>
      <Typography
        component="div"
        sx={{
          color: COLORS[step.status],
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          display: "flex",
          alignItems: "flex-start",
          gap: 0.5,
        }}
      >
        <Box
          component="span"
          sx={
            step.status === "running"
              ? {
                  display: "inline-block",
                  animation: "spin 1s linear infinite",
                }
              : undefined
          }
        >
          {ICONS[step.status]}
        </Box>
        <Box component="span">
          {`${step.label}${summary}`}
        </Box>
      </Typography>
      {showPreview && (
        <Typography
          component="div"
          sx={{
            color:
              step.status === "error"
                ? terminalColors.yellow
                : terminalColors.gray,
            pl: 2,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {`  └ ${preview}`}
        </Typography>
      )}
    </Box>
  );
}
