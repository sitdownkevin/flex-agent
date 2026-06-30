import { Box, Typography } from "@mui/material";
import { sectionAccentSx, terminalColors } from "../theme";
import type { TodoItem } from "../types";

const ICONS: Record<TodoItem["status"], string> = {
  pending: "○",
  in_progress: "●",
  completed: "✓",
};

const COLORS: Record<TodoItem["status"], string> = {
  pending: terminalColors.gray,
  in_progress: terminalColors.yellow,
  completed: terminalColors.green,
};

interface TodosProps {
  title: string;
  items: TodoItem[];
}

export function Todos({ title, items }: TodosProps) {
  if (!items.length) return null;

  return (
    <Box sx={{ my: 1.5, ...sectionAccentSx }}>
      <Typography
        sx={{
          color: terminalColors.magenta,
          fontWeight: 700,
          mb: 0.75,
        }}
      >
        {title}
      </Typography>
      {items.map((item, index) => (
        <Typography
          key={`${item.content}-${index}`}
          sx={{
            color: COLORS[item.status],
            pl: 0.5,
            whiteSpace: "pre-wrap",
            mb: 0.25,
          }}
        >
          {`  ${ICONS[item.status]} ${item.content}`}
        </Typography>
      ))}
    </Box>
  );
}
