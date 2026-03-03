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
    light: 'rgba(51, 112, 255, 0.22)',
    text: '#B8CAFF',
  },

  // 状态颜色 (Status)
  success: {
    main: '#69B184',
    bg: 'rgba(108, 170, 132, 0.16)',
    text: '#A4CFB5',
    dot: '#69B184',
  },
  warning: {
    main: '#C9984D',
    bg: 'rgba(199, 148, 70, 0.18)',
    text: '#D8B473',
    dot: '#C9984D',
  },
  danger: {
    main: '#D86A74',
    bg: 'rgba(216, 106, 116, 0.18)',
    text: '#F3BDC4',
    dot: '#D86A74',
  },
  info: {
    main: '#3370FF',
    bg: 'rgba(51, 112, 255, 0.18)',
    text: '#B8CAFF',
    dot: '#3370FF',
  },

  // 中性颜色 (Neutral)
  gray: {
    50: '#2A2B2D',
    100: '#303236',
    200: '#3A3C40',
    300: '#4A4D52',
    400: '#7F8791',
    500: '#AEB5BE',
    600: '#E8EDF2',
  },

  // 文字颜色 (Text)
  text: {
    primary: '#E8EDF2', // 主文字
    secondary: '#AEB5BE', // 次要文字
    tertiary: '#7F8791', // 辅助文字
    placeholder: '#4A4D52', // 占位符
  },

  // 背景色 (Background)
  bg: {
    primary: '#1B1B1C',
    secondary: '#232324',
    hover: '#303236',
    selected: 'rgba(51, 112, 255, 0.22)',
    disabled: '#2A2B2D',
  },

  // 边框 (Border)
  border: {
    default: '#3A3C40',
    light: '#4A4D52',
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
    dotColor: 'var(--sc-status-neutral-dot)',
    textColor: 'var(--sc-status-neutral-text)',
    bgColor: 'var(--sc-status-neutral-bg)',
  },
  QUEUED: {
    label: '排队中',
    dotColor: 'var(--sc-status-info-dot)',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
  },
  PROCESSING: {
    label: '处理中',
    dotColor: 'var(--sc-status-info-dot)',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
  },
  COMPLETED: {
    label: '已完成',
    dotColor: 'var(--sc-status-success-dot)',
    textColor: 'var(--sc-status-success-text)',
    bgColor: 'var(--sc-status-success-bg)',
  },
  FAILED: {
    label: '失败',
    dotColor: 'var(--sc-status-danger-dot)',
    textColor: 'var(--sc-status-danger-text)',
    bgColor: 'var(--sc-status-danger-bg)',
  },
  DETECTING: {
    label: '检测中',
    dotColor: 'var(--sc-status-info-dot)',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
  },
  REVIEW_PENDING: {
    label: '待审核',
    dotColor: 'var(--sc-status-warning-dot)',
    textColor: 'var(--sc-status-warning-text)',
    bgColor: 'var(--sc-status-warning-bg)',
  },
  REVIEW_APPROVED: {
    label: '已确认',
    dotColor: 'var(--sc-status-approved-dot)',
    textColor: 'var(--sc-status-approved-text)',
    bgColor: 'var(--sc-status-approved-bg)',
  },
  SPLITTING: {
    label: '切分中',
    dotColor: 'var(--sc-status-info-dot)',
    textColor: 'var(--sc-status-info-text)',
    bgColor: 'var(--sc-status-info-bg)',
  },
  TIMELINE_READY: {
    label: '切分完成',
    dotColor: 'var(--sc-status-success-dot)',
    textColor: 'var(--sc-status-success-text)',
    bgColor: 'var(--sc-status-success-bg)',
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

  // 状态（统一来源，供 Tailwind 语义类复用）
  'success-bg': colors.success.bg,
  'warning-bg': colors.warning.bg,
  'danger-bg': colors.danger.bg,
  'info-bg': colors.info.bg,
  'success-text': colors.success.text,
  'warning-text': colors.warning.text,
  'danger-text': colors.danger.text,
  'info-text': colors.info.text,
  'success-border': colors.success.dot,
  'warning-border': colors.warning.dot,
  'danger-border': colors.danger.dot,
  'info-border': colors.info.dot,
}
