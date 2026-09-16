// Imported into the generated Workbox service worker (see vite.config.ts).
self.addEventListener('push', (event) => {
	const data = event.data ? event.data.json() : {};
	event.waitUntil(
		self.registration.showNotification(data.title || '1000 Mots', {
			body: data.body || '',
			icon: '/icons/icon-192.png',
			badge: '/icons/icon-192.png',
			tag: 'review-reminder',
			data: { url: data.url || '/' }
		})
	);
});

self.addEventListener('notificationclick', (event) => {
	event.notification.close();
	const url = new URL(event.notification.data?.url || '/', self.location.origin).href;
	event.waitUntil(
		self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windows) => {
			const existing = windows.find((w) => w.url.startsWith(self.location.origin));
			if (existing) return existing.focus().then((w) => w.navigate(url));
			return self.clients.openWindow(url);
		})
	);
});
