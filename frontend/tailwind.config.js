/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
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
        // App accent (Linear-style lavender-blue, used sparingly: primary buttons, focus, active states).
        // Generated documents keep their own SVNIT navy letterhead; this only themes the website.
        brand: {
          50: '#f4f5fe',
          100: '#e8eafc',
          200: '#d0d4f7',
          300: '#aeb5f0',
          400: '#8f98e6',
          500: '#7681dd',
          600: '#6a75d6',
          700: '#5e6ad2',
          800: '#4e59b8',
          900: '#3c4590',
        },
        // Linear surface ladder: dark sidebar and dark mode
        ink: {
          950: '#08090a',
          900: '#0f1011',
          850: '#141516',
          800: '#18191a',
          750: '#1f2023',
          700: '#23252a',
          600: '#34343a',
          500: '#62666d',
          400: '#8a8f98',
          300: '#d0d6e0',
          200: '#f7f8f8',
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
