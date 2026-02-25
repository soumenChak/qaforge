/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
  ],
  theme: {
    extend: {
      colors: {
        fg: {
          teal: '#2bb8c6',
          tealDark: '#1f99ad',
          tealLight: '#e7f8fa',
          green: '#84bd3f',
          navy: '#142730',
          dark: '#203540',
          mid: '#50606c',
          gray: '#f2f6f8',
        },
      },
      fontFamily: {
        sans: ['Lato', 'Helvetica', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        card: '0 2px 8px rgba(19, 40, 50, 0.10)',
        'card-hover': '0 10px 24px rgba(19, 40, 50, 0.16)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      },
      fontSize: {
        'xxs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
};
