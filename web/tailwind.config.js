/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 纸张主题：页面底色、卡片、分隔线与墨色文字
        paper: {
          DEFAULT: '#f3ead4',
          soft: '#fbf7ec',
          deep: '#ece1c7',
          line: '#ddd0b2',
        },
        ink: {
          DEFAULT: '#3a3226',
          soft: '#74664f',
          faint: '#9c8d74',
        },
        // 墨蓝主色，替代默认亮靛蓝，和纸张底色更协调
        indigo: {
          50: '#eff1f5',
          100: '#dfe4ec',
          200: '#c5ceda',
          300: '#a0aec1',
          400: '#7b8ca4',
          500: '#5f7289',
          600: '#4a5a70',
          700: '#3d4a5d',
          800: '#333d4d',
          900: '#2b3340',
          950: '#1b2029',
        },
        // 暖灰替代默认冷灰，让表格、边框与纸张底色协调
        gray: {
          50: '#faf6ec',
          100: '#f4eddd',
          200: '#e9dec7',
          300: '#d8c8a9',
          400: '#b7a483',
          500: '#92805f',
          600: '#75644a',
          700: '#594b38',
          800: '#41362a',
          900: '#2c251c',
          950: '#1d1811',
        },
        slate: {
          50: '#f7f2e7',
          100: '#efe6d4',
          200: '#e3d6bd',
          300: '#cfbd9b',
          400: '#ac9878',
          500: '#897658',
          600: '#6d5d45',
          700: '#544834',
          800: '#3d3427',
          900: '#2b241b',
          950: '#1c1711',
        },
      },
    },
  },
  plugins: [],
}
