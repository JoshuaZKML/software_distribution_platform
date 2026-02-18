import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Semantic tokens – values mapped from design system
        background: {
          primary: 'rgb(var(--bg-primary) / <alpha-value>)',
          secondary: 'rgb(var(--bg-secondary) / <alpha-value>)',
          surface: 'rgb(var(--bg-surface) / <alpha-value>)',
          'surface-raised': 'rgb(var(--surface-raised) / <alpha-value>)',
          overlay: 'rgb(var(--overlay) / <alpha-value>)',
        },
        text: {
          main: 'rgb(var(--text-main) / <alpha-value>)',
          muted: 'rgb(var(--text-muted) / <alpha-value>)',
          link: 'rgb(var(--link) / <alpha-value>)',
        },
        action: {
          primary: 'rgb(var(--action-primary) / <alpha-value>)',
          hover: 'rgb(var(--action-hover) / <alpha-value>)',
        },
        state: {
          success: 'rgb(var(--state-success) / <alpha-value>)',
          warning: 'rgb(var(--state-warning) / <alpha-value>)',
          error: 'rgb(var(--state-error) / <alpha-value>)',
          'focus-ring': 'rgb(var(--state-focus-ring) / <alpha-value>)',
          disabled: 'rgb(var(--state-disabled) / <alpha-value>)',
        },
        border: {
          subtle: 'rgb(var(--border-subtle) / <alpha-value>)',
          strong: 'rgb(var(--border-strong) / <alpha-value>)',
        },
        // Flat alias for error (so text-error works)
        error: 'rgb(var(--state-error) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter Variable', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      fontSize: {
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.875rem', { lineHeight: '1.25rem' }],
        base: ['1rem', { lineHeight: '1.5rem' }],
        lg: ['1.125rem', { lineHeight: '1.75rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem' }],
      },
      spacing: {
        0: '0px',
        1: '4px',
        2: '8px',
        3: '12px',
        4: '16px',
        5: '20px',
        6: '24px',
        8: '32px',
        10: '40px',
        12: '48px',
        16: '64px',
        20: '80px',
        24: '96px',
      },
      transitionDuration: {
        instant: '80ms',
        fast: '120ms',
        moderate: '200ms',
        slow: '250ms',
        reduced: '0.01s',
      },
      transitionTimingFunction: {
        default: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
};

export default config;