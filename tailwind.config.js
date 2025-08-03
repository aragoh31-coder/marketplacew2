/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './static/src/**/*.js'
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1E293B',
        secondary: '#0F172A',
        accent: '#EAB308',
        neutral: '#F1F5F9',
        success: '#22C55E',
        danger: '#EF4444'
      }
    }
  },
  plugins: []
}
