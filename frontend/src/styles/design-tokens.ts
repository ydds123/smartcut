/**
 * 飞书风格设计系统 - Design Tokens
 *
 * 飞书设计语言参考：https://design.fe.chat/
 */

// ============================================================================
// 颜色系统 (Colors)
// ============================================================================

export const colors = {
  // 主色 (Primary)
  primary: {
    main: '#3370FF',
    hover: '#295AC8',
    active: '#2246A0',
    light: '#E8F3FF',
    text: '#1D4ED8',
  },

  // 状态颜色 (Status)
  success: {
    main: '#00B42A',
    bg: '#E6FFEB',
    text: '#0F766E',
    dot: '#00B42A',
  },
  warning: {
    main: '#FF7D00',
    bg: '#FFF7E8',
    text: '#9A5700',
    dot: '#FF7D00',
  },
  danger: {
    main: '#F53F3F',
    bg: '#FFECE8',
    text: '#B91C1C',
    dot: '#F53F3F',
  },
  info: {
    main: '#91B4FF',
    bg: '#E8F3FF',
    text: '#1D4ED8',
    dot: '#91B4FF',
  },

  // 中性颜色 (Neutral)
  gray: {
    50: '#F7F8FA',
    100: '#F2F3F5',
    200: '#E5E6EB',
    300: '#C9CDD4',
    400: '#86909C',
    500: '#4E5969',
    600: '#1D2129',
  },

  // 文字颜色 (Text)
  text: {
    primary: '#1D2129',    // 主文字
    secondary: '#4E5969',  // 次要文字
    tertiary: '#86909C',   // 辅助文字
    placeholder: '#C9CDD4', // 占位符
  },

  // 背景色 (Background)
  bg: {
    primary: '#FFFFFF',
    secondary: '#F7F8FA',
    hover: '#F2F3F5',
    selected: '#E8F3FF',
    disabled: '#F2F3F5',
  },

  // 边框 (Border)
  border: {
    default: '#E5E6EB',
    light: '#F2F3F5',
    focus: '#3370FF',
  },
}

// ============================================================================
// 字体系统 (Typography)
// ============================================================================

export const typography = {
  fontFamily: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },

  fontSize: {
    h1: '20px',
    h2: '16px',
    h3: '14px',
    body: '14px',
    small: '12px',
    caption: '12px',
  },

  fontWeight: {
    medium: 500,
    semibold: 600,
    bold: 700,
  },

  lineHeight: {
    tight: '20px',
    normal: '22px',
    relaxed: '28px',
  },
}

// ============================================================================
// 间距系统 (Spacing)
// ============================================================================

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '20px',
  xxl: '24px',
}

// ============================================================================
// 圆角 (Border Radius)
// ============================================================================

export const borderRadius = {
  sm: '4px',   // 小圆角（按钮、标签）
  md: '6px',   // 中圆角（卡片、缩略图）
  lg: '8px',   // 大圆角（弹窗）
  xl: '12px',  // 超大圆角
  full: '9999px',
}

// ============================================================================
// 阴影 (Shadows)
// ============================================================================

export const shadow = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
}

// ============================================================================
// 过渡动画 (Transitions)
// ============================================================================

export const transition = {
  fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
  normal: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
  slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
}

// ============================================================================
// 状态配置 (Status Config)
// ============================================================================

export const statusConfig = {
  PENDING: {
    label: '等待中',
    dotColor: colors.gray[300],
    textColor: colors.text.secondary,
    bgColor: colors.gray[100],
  },
  QUEUED: {
    label: '排队中',
    dotColor: colors.info.dot,
    textColor: colors.info.text,
    bgColor: colors.info.bg,
  },
  PROCESSING: {
    label: '处理中',
    dotColor: colors.primary.main,
    textColor: colors.primary.text,
    bgColor: colors.primary.light,
  },
  COMPLETED: {
    label: '已完成',
    dotColor: colors.success.dot,
    textColor: colors.success.text,
    bgColor: colors.success.bg,
  },
  FAILED: {
    label: '失败',
    dotColor: colors.danger.dot,
    textColor: colors.danger.text,
    bgColor: colors.danger.bg,
  },
  DETECTING: {
    label: '检测中',
    dotColor: colors.info.dot,
    textColor: colors.info.text,
    bgColor: colors.info.bg,
  },
  REVIEW_PENDING: {
    label: '待审核',
    dotColor: colors.warning.dot,
    textColor: colors.warning.text,
    bgColor: colors.warning.bg,
  },
  REVIEW_APPROVED: {
    label: '已确认',
    dotColor: colors.info.dot,
    textColor: colors.info.text,
    bgColor: colors.info.bg,
  },
  SPLITTING: {
    label: '切分中',
    dotColor: colors.primary.main,
    textColor: colors.primary.text,
    bgColor: colors.primary.light,
  },
  TIMELINE_READY: {
    label: '切分完成',
    dotColor: colors.success.dot,
    textColor: colors.success.text,
    bgColor: colors.success.bg,
  },
} as const

// ============================================================================
// Tailwind CSS 配置映射
// ============================================================================

/**
 * 用于扩展 tailwind.config.js 的颜色
 */
export const tailwindColors = {
  primary: colors.primary.main,
  'primary-hover': colors.primary.hover,
  'primary-light': colors.primary.light,

  success: colors.success.main,
  warning: colors.warning.main,
  danger: colors.danger.main,
  info: colors.info.main,

  // 灰度
  gray: {
    50: colors.gray[50],
    100: colors.gray[100],
    200: colors.gray[200],
    300: colors.gray[300],
    400: colors.gray[400],
    500: colors.gray[500],
    600: colors.gray[600],
  },

  // 文字
  'text-primary': colors.text.primary,
  'text-secondary': colors.text.secondary,
  'text-tertiary': colors.text.tertiary,

  // 背景
  'bg-primary': colors.bg.primary,
  'bg-secondary': colors.bg.secondary,
  'bg-hover': colors.bg.hover,
  'bg-selected': colors.bg.selected,

  // 边框
  'border-default': colors.border.default,
  'border-light': colors.border.light,
  'border-focus': colors.border.focus,
}
