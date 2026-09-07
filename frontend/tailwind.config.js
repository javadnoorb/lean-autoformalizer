/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        lean: {
          50: '#f4f6fa',
          100: '#e8edf5',
          500: '#2b5c92',
          600: '#1e446d',
          700: '#163353',
          800: '#0f243c',
          900: '#091523',
        }
      }
    },
  },
  plugins: [],
}
