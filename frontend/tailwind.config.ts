import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'rgb(var(--border) / <alpha-value>)',
        input: 'rgb(var(--input) / <alpha-value>)',
        ring: 'rgb(var(--ring) / <alpha-value>)',
        background: 'rgb(var(--background) / <alpha-value>)',
        foreground: 'rgb(var(--foreground) / <alpha-value>)',
        primary: {
          DEFAULT: 'rgb(var(--primary) / <alpha-value>)',
          foreground: 'rgb(var(--primary-foreground) / <alpha-value>)',
        },
        secondary: {
          DEFAULT: 'rgb(var(--secondary) / <alpha-value>)',
          foreground: 'rgb(var(--secondary-foreground) / <alpha-value>)',
        },
        destructive: {
          DEFAULT: 'rgb(var(--destructive) / <alpha-value>)',
          foreground: 'rgb(var(--destructive-foreground) / <alpha-value>)',
        },
        muted: {
          DEFAULT: 'rgb(var(--muted) / <alpha-value>)',
          foreground: 'rgb(var(--muted-foreground) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          foreground: 'rgb(var(--accent-foreground) / <alpha-value>)',
        },
        popover: {
          DEFAULT: 'rgb(var(--popover) / <alpha-value>)',
          foreground: 'rgb(var(--popover-foreground) / <alpha-value>)',
        },
        card: {
          DEFAULT: 'rgb(var(--card) / <alpha-value>)',
          foreground: 'rgb(var(--card-foreground) / <alpha-value>)',
        },
        // Added error color referencing the destructive CSS variable
        error: 'rgb(var(--destructive) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        'marketing-xs': ['0.75rem', { lineHeight: '1rem' }],
        'marketing-sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'marketing-base': ['1rem', { lineHeight: '1.5rem' }],
        'marketing-lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'marketing-xl': ['1.25rem', { lineHeight: '1.75rem' }],
        'marketing-2xl': ['1.5rem', { lineHeight: '2rem' }],
        'marketing-3xl': ['1.875rem', { lineHeight: '2.25rem' }],
        'marketing-4xl': ['2.25rem', { lineHeight: '2.5rem' }],
        'marketing-5xl': ['3rem', { lineHeight: '1' }],
        'marketing-6xl': ['3.75rem', { lineHeight: '1' }],
        'app-xs': ['0.75rem', { lineHeight: '1rem' }],
        'app-sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'app-base': ['1rem', { lineHeight: '1.5rem' }],
        'app-lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'app-xl': ['1.25rem', { lineHeight: '1.75rem' }],
        'app-2xl': ['1.5rem', { lineHeight: '2rem' }],
      },
    },
  },
  plugins: [require('@tailwindcss/forms'), require('@tailwindcss/typography')],
};
export default config;