module.exports = {
  mode: 'jit',
  content: [
    './templates/**/*.html',
    './**/*.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          900: '#1e3a8a',
        },
        dark: {
          bg: '#121212',
          card: '#1E1E1E',
          text: '#E4E6EB',
        },
        tor: {
          dark: '#0d1117',
          medium: '#161b22',
          light: '#21262d',
          accent: '#58a6ff',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-down': 'slideDown 0.3s ease-out',
      },
      fontFamily: {
        'system': ['-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/container-queries'),
  ],
  safelist: [
    'bg-tor-dark',
    'bg-tor-medium',
    'bg-tor-light',
    'text-tor-accent',
    'border-tor-accent',
    'bg-dark-bg',
    'text-dark-text',
  ],
};
