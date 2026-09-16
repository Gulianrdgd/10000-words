/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				brand: {
					50: '#eef4ff',
					100: '#d9e6ff',
					200: '#b3ccff',
					300: '#82abff',
					400: '#5588f5',
					500: '#3366e0',
					600: '#264fb8',
					700: '#1e3e91',
					800: '#1c3570',
					900: '#1a2f5c'
				}
			}
		}
	},
	plugins: []
};
