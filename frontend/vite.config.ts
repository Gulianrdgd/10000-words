import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: '1000 Mots — French Vocabulary',
				short_name: '1000 Mots',
				description: 'Learn the 1000 most frequent French words with spaced repetition.',
				theme_color: '#0f0e0c',
				background_color: '#0f0e0c',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
					{ src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
				]
			},
			// serve the SPA shell for any route when offline (adapter-static fallback page)
			kit: {
				adapterFallback: 'index.html'
			},
			workbox: {
				// fonts: only the latin subsets, which cover French
				globPatterns: ['**/*.{js,css,html,ico,png,svg,webmanifest}', '**/*-latin-*.woff2'],
				// push notification + notification click handlers
				importScripts: ['push-sw.js']
			},
			devOptions: {
				enabled: true,
				// importScripts needs a classic (non-module) worker
				type: 'classic'
			}
		})
	],
	server: {
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	}
});
