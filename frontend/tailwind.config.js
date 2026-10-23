/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      colors: {
        // SVNIT navy, the single brand accent used across the app
        brand: {
          50: '#f2f5f9',
          100: '#e3e9f2',
          200: '#c3d0e2',
          300: '#94abcb',
          500: '#3a5a86',
          600: '#27466f',
          700: '#1b365d',
          800: '#142a49',
          900: '#0e1d33',
        },
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        svnit: {
          blue: '#1b365d',
          gold: '#c59b27',
          dark: '#0f172a',
        }
      },
      // One elevation scale for the whole app: hairline cards, raised hovers, floating menus/dialogs
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 1px 3px rgba(16, 24, 40, 0.04)',
        raised: '0 4px 12px -2px rgba(16, 24, 40, 0.08), 0 2px 4px -2px rgba(16, 24, 40, 0.04)',
        popover: '0 12px 32px -6px rgba(16, 24, 40, 0.18), 0 4px 8px -4px rgba(16, 24, 40, 0.06)',
      },
      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        shimmer: 'shimmer 1.4s infinite',
      },
    },
  },
  plugins: [],
}
