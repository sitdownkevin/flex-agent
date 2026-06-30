import { Box, Typography } from "@mui/material";
import { terminalColors } from "../theme";
import type { TimelineEntry, StepRecord } from "../types";
import { StepLine } from "./StepLine";

interface TimelineProps {
  entry: TimelineEntry;
  step?: StepRecord;
}

export function Timeline({ entry, step }: TimelineProps) {
  if (entry.kind === "user") {
    return (
      <Box
        sx={{
          mb: 1,
          pl: 1.25,
          borderLeft: `2px solid ${terminalColors.cyan}`,
        }}
      >
        <Typography
          sx={{
            color: terminalColors.cyan,
            fontWeight: 700,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {`> ${entry.text}`}
        </Typography>
      </Box>
    );
  }

  if (entry.kind === "assistant") {
    return (
      <Box sx={{ mb: 1, pl: 1.25 }}>
        <Typography
          sx={{
            color: terminalColors.text,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {entry.text}
        </Typography>
      </Box>
    );
  }

  if (entry.kind === "system") {
    return (
      <Typography
        sx={{
          color: terminalColors.gray,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          mb: 0.75,
          fontSize: "0.85rem",
        }}
      >
        {entry.text}
      </Typography>
    );
  }

  if (entry.kind === "progress") {
    return (
      <Typography
        sx={{
          color: terminalColors.gray,
          opacity: 0.85,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          mb: 0.5,
          fontSize: "0.8rem",
        }}
      >
        {`› ${entry.text}`}
      </Typography>
    );
  }

  if (entry.kind === "error") {
    return (
      <Box
        sx={{
          mb: 1,
          pl: 1.25,
          borderLeft: `2px solid ${terminalColors.yellow}`,
        }}
      >
        <Typography
          sx={{
            color: terminalColors.yellow,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {`error: ${entry.text}`}
        </Typography>
      </Box>
    );
  }

  if (entry.kind === "step" && step) {
    return (
      <Box sx={{ mb: 0.5, pl: 0.5 }}>
        <StepLine step={step} />
      </Box>
    );
  }

  return (
    <Typography
      sx={{
        color: terminalColors.text,
        whiteSpace: "pre-wrap",
        mb: 0.5,
      }}
    >
      {entry.text}
    </Typography>
  );
}
