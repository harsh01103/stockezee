export function roundToStep(value: number, step: number) {
  return Math.round(value / step) * step;
}

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function hashString(input: string) {
  let hash = 0;
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash * 31 + input.charCodeAt(index)) >>> 0;
  }
  return hash;
}

export function seededUnit(seed: string) {
  const hash = hashString(seed);
  return (Math.sin(hash) + 1) / 2;
}

export function formatExpiry(date: Date) {
  return date.toISOString().slice(0, 10);
}

export function getUpcomingExpiries(count = 6) {
  const expiries: string[] = [];
  const cursor = new Date();
  cursor.setUTCHours(0, 0, 0, 0);

  while (expiries.length < count) {
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    if (cursor.getUTCDay() === 4) {
      expiries.push(formatExpiry(cursor));
    }
  }

  return expiries;
}

export function getMarketStatus(now = new Date()) {
  const ist = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const day = ist.getDay();
  const minutes = ist.getHours() * 60 + ist.getMinutes();

  if (day === 0 || day === 6) return "closed" as const;
  if (minutes >= 540 && minutes < 555) return "pre-open" as const;
  if (minutes >= 555 && minutes <= 930) return "open" as const;
  if (minutes > 930 && minutes <= 960) return "after-hours" as const;
  return "closed" as const;
}
