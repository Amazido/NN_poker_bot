import { apiFetch, getToken, setToken } from './http';
import { getTelegramWebApp } from './telegram';

const DEV_NAME_KEY = 'op_dev_username';

export interface Me {
  id: string;
  user_type: string;
  telegram_id: number | null;
  telegram_username: string | null;
  balance: number;
}

let loginPromise: Promise<void> | null = null;

/**
 * Получить JWT, если его ещё нет. React StrictMode в dev вызывает эффекты дважды —
 * без дедупликации это шлёт два параллельных /auth/dev с одним именем и роняет
 * бэк (get_dev_by_username падает на MultipleResultsFound).
 */
export function ensureLoggedIn(): Promise<void> {
  if (getToken()) return Promise.resolve();
  if (!loginPromise) {
    loginPromise = login().finally(() => {
      loginPromise = null;
    });
  }
  return loginPromise;
}

/**
 * Получить JWT: через настоящую Telegram initData, а вне Telegram (локальная
 * разработка) — через /auth/dev. Второе работает только если бэк поднят с DEBUG=true.
 */
async function login(): Promise<void> {
  const tg = getTelegramWebApp();
  const initData = tg?.initData;
  if (initData) {
    const res = await apiFetch<{ token: string }>('/auth/telegram', {
      method: 'POST',
      body: { init_data: initData },
      auth: false,
    });
    setToken(res.token);
    return;
  }

  if (!import.meta.env.DEV) {
    throw new Error('Приложение открыто не из Telegram — авторизация недоступна');
  }
  let name = localStorage.getItem(DEV_NAME_KEY);
  if (!name) {
    name = window.prompt('Дев-режим: имя тестового игрока', 'Тестер') || 'Тестер';
    localStorage.setItem(DEV_NAME_KEY, name);
  }
  const res = await apiFetch<{ token: string }>('/auth/dev', {
    method: 'POST',
    body: { username: name },
    auth: false,
  });
  setToken(res.token);
}

export function getMe(): Promise<Me> {
  return apiFetch<Me>('/auth/me');
}

/** Токен подключения к Centrifugo (живёт 60 минут на бэке — вызывать повторно для рефреша). */
export function getCentrifugoToken(): Promise<string> {
  return apiFetch<{ token: string }>('/auth/centrifugo-token').then((r) => r.token);
}
