import { tailwindColors } from './src/styles/design-tokens.ts'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 飞书风格颜色系统
        primary: tailwindColors.primary,
        'primary-hover': tailwindColors['primary-hover'],
        'primary-light': tailwindColors['primary-light'],

        success: tailwindColors.success,
        warning: tailwindColors.warning,
        danger: tailwindColors.danger,
        info: tailwindColors.info,

        // 灰度
        gray: {
          50: tailwindColors.gray['50'],
          100: tailwindColors.gray['100'],
          200: tailwindColors.gray['200'],
          300: tailwindColors.gray['300'],
          400: tailwindColors.gray['400'],
          500: tailwindColors.gray['500'],
          600: tailwindColors.gray['600'],
          700: tailwindColors.gray['600'],
          800: tailwindColors.gray['600'],
          900: tailwindColors.gray['600'],
        },

        // 文字
        'text-primary': tailwindColors['text-primary'],
        'text-secondary': tailwindColors['text-secondary'],
        'text-tertiary': tailwindColors['text-tertiary'],

        // 背景
        'bg-primary': tailwindColors['bg-primary'],
        'bg-secondary': tailwindColors['bg-secondary'],
        'bg-hover': tailwindColors['bg-hover'],
        'bg-selected': tailwindColors['bg-selected'],

        // 边框
        'border-default': tailwindColors['border-default'],
        'border-light': tailwindColors['border-light'],
        'border-focus': tailwindColors['border-focus'],

        // 状态背景（暗色主题）
        'success-bg': tailwindColors['success-bg'],
        'warning-bg': tailwindColors['warning-bg'],
        'danger-bg': tailwindColors['danger-bg'],
        'info-bg': tailwindColors['info-bg'],

        // 状态文字（暗色主题）
        'success-text': tailwindColors['success-text'],
        'warning-text': tailwindColors['warning-text'],
        'danger-text': tailwindColors['danger-text'],
        'info-text': tailwindColors['info-text'],

        // 状态边框（暗色主题）
        'success-border': tailwindColors['success-border'],
        'warning-border': tailwindColors['warning-border'],
        'danger-border': tailwindColors['danger-border'],
        'info-border': tailwindColors['info-border'],
      },

      // 字体
      fontSize: {
        h1: ['20px', { lineHeight: '28px', fontWeight: '600' }],
        h2: ['16px', { lineHeight: '24px', fontWeight: '600' }],
        h3: ['14px', { lineHeight: '22px', fontWeight: '600' }],
        body: ['14px', { lineHeight: '22px', fontWeight: '400' }],
        small: ['12px', { lineHeight: '20px', fontWeight: '400' }],
        caption: ['12px', { lineHeight: '18px', fontWeight: '400' }],
      },

      // 间距
      spacing: {
        '18': '4.5rem', // 72px
      },

      // 圆角
      borderRadius: {
        'xl': '12px',
      },

      // 过渡
      transitionDuration: {
        '150': '150ms',
        '300': '300ms',
      },

      // 阴影
      boxShadow: {
        'feish': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      },
    },
  },
  plugins: [],
}
