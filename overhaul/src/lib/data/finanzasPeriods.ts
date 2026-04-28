import type { Period, PeriodRange } from './finanzas';

const MONTH_NAMES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

export function todayInGT(): Date {
  return new Date();
}

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function periodToDateRange(period: Period, customStart?: string, customEnd?: string): PeriodRange {
  const today = todayInGT();
  const isoToday = isoDate(today);

  switch (period) {
    case 'today':
      return { start: isoToday, end: isoToday, label: 'Hoy' };

    case '7d': {
      const start = new Date(today);
      start.setDate(start.getDate() - 6);
      return { start: isoDate(start), end: isoToday, label: 'Últimos 7 días' };
    }

    case '30d': {
      const start = new Date(today);
      start.setDate(start.getDate() - 29);
      return { start: isoDate(start), end: isoToday, label: 'Últimos 30 días' };
    }

    case 'month': {
      const start = new Date(today.getFullYear(), today.getMonth(), 1);
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return {
        start: isoDate(start),
        end: isoDate(end),
        label: `${MONTH_NAMES[today.getMonth()]} ${today.getFullYear()}`,
      };
    }

    case 'last_month': {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      return {
        start: isoDate(start),
        end: isoDate(end),
        label: `${MONTH_NAMES[start.getMonth()]} ${start.getFullYear()}`,
      };
    }

    case 'ytd': {
      const start = new Date(today.getFullYear(), 0, 1);
      return {
        start: isoDate(start),
        end: isoToday,
        label: `YTD ${today.getFullYear()}`,
      };
    }

    case 'lifetime':
      return { start: '2026-03-01', end: isoToday, label: 'Lifetime (desde marzo 2026)' };

    case 'custom':
      if (!customStart || !customEnd) throw new Error('custom period requires start + end');
      return { start: customStart, end: customEnd, label: `${customStart} → ${customEnd}` };
  }
}

export function daysBetween(startIso: string, endIso: string): number {
  const start = new Date(startIso);
  const end = new Date(endIso);
  return Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;
}

export function previousPeriodRange(range: PeriodRange): PeriodRange {
  const lengthDays = daysBetween(range.start, range.end);
  const prevEnd = new Date(range.start);
  prevEnd.setDate(prevEnd.getDate() - 1);
  const prevStart = new Date(prevEnd);
  prevStart.setDate(prevStart.getDate() - (lengthDays - 1));
  return {
    start: isoDate(prevStart),
    end: isoDate(prevEnd),
    label: `período anterior (${lengthDays}d)`,
  };
}
