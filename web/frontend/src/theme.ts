import { createTheme } from "@mui/material/styles";

export const terminalColors = {
  bg: "#0d1117",
  text: "#c9d1d9",
  cyan: "#39c5cf",
  green: "#3fb950",
  yellow: "#d29922",
  red: "#f85149",
  gray: "#8b949e",
  magenta: "#bc8cff",
  border: "#21262d",
  panel: "#161b22",
};

export const monoFont =
  '"JetBrains Mono", "Fira Code", "SF Mono", Menlo, Monaco, Consolas, monospace';

export const sectionAccentSx = {
  borderLeft: `3px solid ${terminalColors.cyan}`,
  pl: 1.5,
  ml: 0,
};

export const cardSx = {
  bgcolor: terminalColors.panel,
  border: `1px solid ${terminalColors.border}`,
  borderRadius: 1.5,
  boxShadow: "0 1px 2px rgba(0,0,0,0.3)",
  transition: "border-color 200ms ease",
  "&:hover": {
    borderColor: "rgba(57, 197, 207, 0.3)",
  },
};

const TOOLBAR_HEIGHT = 28;

/** 顶栏 / 工具条 Chip 统一样式 */
export const toolbarChipSx = {
  height: TOOLBAR_HEIGHT,
  fontSize: "0.72rem",
  borderRadius: 1,
  border: `1px solid ${terminalColors.border}`,
  bgcolor: "rgba(255,255,255,0.04)",
  color: terminalColors.gray,
  "& .MuiChip-label": { px: 1, py: 0 },
};

/** 顶栏 / 工具条 Button 统一样式 */
export const toolbarButtonSx = {
  height: TOOLBAR_HEIGHT,
  minHeight: TOOLBAR_HEIGHT,
  fontSize: "0.72rem",
  px: 1.25,
  py: 0,
  lineHeight: 1,
  borderRadius: 1,
  borderColor: terminalColors.border,
  color: terminalColors.text,
  bgcolor: "rgba(255,255,255,0.04)",
  whiteSpace: "nowrap" as const,
  "&:hover": {
    borderColor: terminalColors.cyan,
    bgcolor: "rgba(57, 197, 207, 0.08)",
  },
};

/** 顶栏菜单 IconButton 统一样式 */
export const toolbarIconButtonSx = {
  width: TOOLBAR_HEIGHT,
  height: TOOLBAR_HEIGHT,
  p: 0,
  flexShrink: 0,
  border: `1px solid ${terminalColors.border}`,
  borderRadius: 1,
  bgcolor: "rgba(255,255,255,0.04)",
  color: terminalColors.gray,
  "&:hover": {
    borderColor: terminalColors.cyan,
    bgcolor: "rgba(57, 197, 207, 0.08)",
    color: terminalColors.text,
  },
};

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: terminalColors.cyan },
    secondary: { main: terminalColors.magenta },
    background: {
      default: terminalColors.bg,
      paper: terminalColors.panel,
    },
    text: {
      primary: terminalColors.text,
      secondary: terminalColors.gray,
    },
    error: { main: terminalColors.red },
    warning: { main: terminalColors.yellow },
    success: { main: terminalColors.green },
  },
  typography: {
    fontFamily: monoFont,
    fontSize: 13,
  },
  shape: { borderRadius: 4 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "@keyframes spin": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "@keyframes blink": {
          "0%, 49%": { opacity: 1 },
          "50%, 100%": { opacity: 0 },
        },
        body: {
          backgroundColor: terminalColors.bg,
          margin: 0,
        },
        "#root": {
          minHeight: "100vh",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          border: `1px solid ${terminalColors.border}`,
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontFamily: monoFont,
          fontSize: "0.75rem",
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          fontFamily: monoFont,
        },
      },
    },
  },
});
