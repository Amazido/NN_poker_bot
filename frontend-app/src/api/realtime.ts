import { Centrifuge } from 'centrifuge';
import { getCentrifugoToken } from './auth';

const URL = import.meta.env.VITE_CENTRIFUGO_URL as string | undefined;
// TODO(бэк): вынести префикс из /auth/centrifugo-token (готовые имена каналов),
// чтобы фронт не знал про namespace dev/prod вручную.
const PREFIX = (import.meta.env.VITE_CENTRIFUGO_PREFIX as string | undefined) ?? 'dev';

export function chRoom(roomId: string): string {
  return `${PREFIX}:room:${roomId}`;
}
export function chUser(userId: string): string {
  return `${PREFIX}:user#${userId}`;
}

let client: Centrifuge | null = null;
let connectPromise: Promise<Centrifuge> | null = null;

function createClient(): Centrifuge {
  return new Centrifuge(URL!, {
    getToken: () => getCentrifugoToken(),
  });
}

/** Подключиться (однократно на сессию) и подождать успешного connect. Бросает при таймауте/ошибке. */
export function connectRealtime(timeoutMs = 5000): Promise<Centrifuge> {
  if (!URL) return Promise.reject(new Error('VITE_CENTRIFUGO_URL не задан'));
  if (client && client.state === 'connected') return Promise.resolve(client);
  if (connectPromise) return connectPromise;

  const c = client ?? createClient();
  client = c;

  connectPromise = new Promise<Centrifuge>((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('Centrifugo connect timeout'));
    }, timeoutMs);

    function onConnected() {
      cleanup();
      resolve(c);
    }
    function onError(ctx: unknown) {
      cleanup();
      reject(ctx instanceof Error ? ctx : new Error('Centrifugo connect error'));
    }
    function cleanup() {
      clearTimeout(timer);
      c.off('connected', onConnected);
      c.off('error', onError);
    }

    c.on('connected', onConnected);
    c.on('error', onError);
    c.connect();
  }).finally(() => {
    connectPromise = null;
  });

  return connectPromise;
}

/** Подписка на канал с обработчиком публикаций. Возвращает функцию отписки. */
export function subscribeChannel(channel: string, onData: (data: unknown) => void): () => void {
  if (!client) throw new Error('Centrifugo client не подключен — вызови connectRealtime() сначала');
  const existing = client.getSubscription(channel);
  const sub = existing ?? client.newSubscription(channel);
  sub.on('publication', (ctx) => onData(ctx.data));
  sub.subscribe();
  return () => {
    sub.unsubscribe();
    client?.removeSubscription(sub);
  };
}
