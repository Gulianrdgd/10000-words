export function weekStartISO(d: Date = new Date()): string {
	const day = (d.getDay() + 6) % 7; // Monday = 0
	const monday = new Date(d);
	monday.setDate(d.getDate() - day);
	monday.setHours(0, 0, 0, 0);
	return toLocalISO(monday);
}

/** toISOString() would convert local midnight to UTC first, so east of
 *  Greenwich Monday 00:30 comes back as the previous Sunday — shifting the
 *  whole goals week by one day. */
function toLocalISO(d: Date): string {
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${d.getFullYear()}-${month}-${day}`;
}

export function addDays(iso: string, days: number): string {
	const d = new Date(iso + 'T00:00:00');
	d.setDate(d.getDate() + days);
	return toLocalISO(d);
}
