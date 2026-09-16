/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				// warm off-black neutrals; one family for every gray in the app
				ink: {
					950: '#0f0e0c',
					900: '#171614',
					850: '#1d1b18',
					800: '#25231f',
					700: '#34312c',
					600: '#4a463f',
					500: '#716b61',
					400: '#9a9387',
					300: '#bfb8ab',
					200: '#ddd6c9',
					100: '#f0eadf'
				},
				// the single accent: primary actions, active states, charts
				paper: {
					DEFAULT: '#f1e6cf',
					dim: '#d9c9a8'
				},
				// grammatical gender, used as a memory cue on articles
				masc: '#8fb3d9',
				fem: '#e39a9a',
				// answer feedback
				good: '#9cc49a',
				bad: '#df9a72'
			},
			fontFamily: {
				sans: ['"Geist Variable"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
				serif: ['"Fraunces Variable"', 'ui-serif', 'Georgia', 'serif']
			},
			borderRadius: {
				card: '1.25rem'
			},
			keyframes: {
				enter: {
					from: { opacity: '0', transform: 'translateY(6px)' },
					to: { opacity: '1', transform: 'none' }
				},
				rise: {
					from: { transform: 'translateY(100%)' },
					to: { transform: 'none' }
				}
			},
			animation: {
				enter: 'enter 320ms cubic-bezier(0.2, 0.8, 0.2, 1) both',
				rise: 'rise 260ms cubic-bezier(0.2, 0.8, 0.2, 1) both'
			}
		}
	},
	plugins: []
};
