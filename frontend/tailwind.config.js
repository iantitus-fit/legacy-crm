/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Legacy navy palette — kept for backward compat during migration
        navy: {
          900: '#0F172A',
          800: '#1E293B',
          700: '#334155',
          600: '#475569',
        },
        // Sprint 15 — semantic theme tokens backed by CSS variables.
        // Each value maps to a var(--...) so they swap when data-theme
        // changes on <html>.
        surface: {
          DEFAULT: 'var(--bg-surface)',
          hover: 'var(--bg-surface-hover)',
        },
        page: 'var(--bg-primary)',
        'page-secondary': 'var(--bg-secondary)',
        sidebar: {
          DEFAULT: 'var(--sidebar-bg)',
          hover: 'var(--sidebar-hover-bg)',
          border: 'var(--sidebar-border)',
        },
        input: 'var(--bg-input)',
        modal: 'var(--bg-modal)',
        // Text
        'th-text': {
          DEFAULT: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          inverse: 'var(--text-inverse)',
        },
        // Borders
        'th-border': {
          DEFAULT: 'var(--border-primary)',
          secondary: 'var(--border-secondary)',
          focus: 'var(--border-focus)',
        },
        // Brand
        brand: {
          purple: 'var(--brand-purple)',
          'purple-hover': 'var(--brand-purple-hover)',
          'purple-light': 'var(--brand-purple-light)',
          'purple-text': 'var(--brand-purple-text)',
          teal: 'var(--brand-teal)',
          'teal-hover': 'var(--brand-teal-hover)',
          'teal-light': 'var(--brand-teal-light)',
          'teal-text': 'var(--brand-teal-text)',
        },
        // Sidebar text
        'sidebar-text': {
          DEFAULT: 'var(--sidebar-text)',
          active: 'var(--sidebar-text-active)',
          section: 'var(--sidebar-section-label)',
        },
        // Cards
        card: {
          DEFAULT: 'var(--card-bg)',
          border: 'var(--card-border)',
          hover: 'var(--card-hover-bg)',
        },
        // Badges
        'badge-success': { bg: 'var(--badge-success-bg)', text: 'var(--badge-success-text)' },
        'badge-warning': { bg: 'var(--badge-warning-bg)', text: 'var(--badge-warning-text)' },
        'badge-danger':  { bg: 'var(--badge-danger-bg)',  text: 'var(--badge-danger-text)' },
        'badge-info':    { bg: 'var(--badge-info-bg)',    text: 'var(--badge-info-text)' },
        // Buttons
        'btn-primary': { bg: 'var(--btn-primary-bg)', text: 'var(--btn-primary-text)', hover: 'var(--btn-primary-hover)' },
        'btn-secondary': { bg: 'var(--btn-secondary-bg)', text: 'var(--btn-secondary-text)', border: 'var(--btn-secondary-border)', hover: 'var(--btn-secondary-hover-bg)' },
        'btn-danger': { bg: 'var(--btn-danger-bg)', text: 'var(--btn-danger-text)' },
        // FAB
        fab: { DEFAULT: 'var(--fab-bg)', text: 'var(--fab-text)', hover: 'var(--fab-hover)' },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'th-sm': 'var(--shadow-sm)',
        'th-md': 'var(--shadow-md)',
        'th-lg': 'var(--shadow-lg)',
      },
    },
  },
  plugins: [],
}
