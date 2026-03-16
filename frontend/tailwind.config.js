/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx,ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'page-bg':      '#0f172a',
        'card-bg':      '#1e293b',
        'card-border':  '#334155',
        'text-primary': '#f1f5f9',
        'text-secondary':'#94a3b8',
        'text-muted':   '#64748b',
        profit:  '#10b981',
        loss:    '#ef4444',
        signal:  '#6366f1',
        warning: '#f59e0b',
        info:    '#3b82f6',
      },
      fontFamily: {
        sans:    ['Inter', 'sans-serif'],
        heading: ['Inter', 'sans-serif'],
        mono:    ['JetBrains Mono', 'Fira Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.4)',
        glow: '0 0 12px rgba(16,185,129,0.3)',
      },
    },
  },
  plugins: [],
}
