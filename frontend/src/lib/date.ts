export function weekStartISO(d: Date = new Date()): string {
	const day = (d.getDay() + 6) % 7; // Monday = 0
	const monday = new Date(d);
	monday.setDate(d.getDate() - day);
	monday.setHours(0, 0, 0, 0);
	return monday.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
	const d = new Date(iso + 'T00:00:00');
	d.setDate(d.getDate() + days);
	return d.toISOString().slice(0, 10);
}
