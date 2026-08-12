import { apiFetch } from './http';
import type { CardCode, PrivateView, PublicView } from '../types/game';

export function createRoom(): Promise<PublicView> {
  return apiFetch<PublicView>('/rooms', { method: 'POST', body: {} });
}

export function joinRoom(joinCode: string): Promise<PublicView> {
  return apiFetch<PublicView>('/rooms/join', { method: 'POST', body: { join_code: joinCode.trim().toUpperCase() } });
}

export function startMatch(roomId: string): Promise<PublicView> {
  return apiFetch<PublicView>(`/rooms/${roomId}/start`, { method: 'POST' });
}

/** В лобби — уходишь совсем. В активном матче — место остаётся, доигрывает авто-ход. */
export function leaveRoomApi(roomId: string): Promise<PublicView> {
  return apiFetch<PublicView>(`/rooms/${roomId}/leave`, { method: 'POST' });
}

export function bid(roomId: string, value: number): Promise<PublicView> {
  return apiFetch<PublicView>(`/rooms/${roomId}/action`, {
    method: 'POST',
    body: { action_type: 'bid', payload: { bid: value } },
  });
}

export function playCard(roomId: string, card: CardCode): Promise<PublicView> {
  return apiFetch<PublicView>(`/rooms/${roomId}/action`, {
    method: 'POST',
    body: { action_type: 'play_card', payload: { card } },
  });
}

export function getPublicView(roomId: string): Promise<PublicView> {
  return apiFetch<PublicView>(`/rooms/${roomId}`);
}

export function getPrivateView(roomId: string): Promise<PrivateView> {
  return apiFetch<PrivateView>(`/rooms/${roomId}/hand`);
}
