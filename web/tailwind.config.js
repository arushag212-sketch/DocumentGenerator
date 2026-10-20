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
      }
    },
  },
  plugins: [],
}
