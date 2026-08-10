interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { start_param?: string; [k: string]: unknown };
  ready(): void;
  expand(): void;
  colorScheme: 'light' | 'dark';
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp };
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

/** room_id, переданный ботом через deep-link (?startapp=... в ссылке на бота). */
export function getStartParam(): string | null {
  return getTelegramWebApp()?.initDataUnsafe.start_param ?? null;
}
