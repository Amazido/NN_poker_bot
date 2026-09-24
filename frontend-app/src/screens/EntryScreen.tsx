import { useEffect, useState } from 'react';
import { AppHeader } from '../components/AppHeader';
import { TableRulesForm } from '../components/TableRulesForm';
import { getRulesPresets } from '../api/rooms';
import {
  FALLBACK_LIMITS,
  FALLBACK_SETTINGS,
  clampSettings,
  roundsTotal,
  settingsError,
} from '../lib/rulesForm';
import type { RulesPreset, RulesPresetsResponse, TableRulesSettings } from '../types/game';
import styles from './EntryScreen.module.css';

export interface EntryScreenProps {
  onCreate: (opts: { rulesCode?: string; rules?: TableRulesSettings }) => void;
  onJoin: (code: string) => void;
  busy?: boolean;
  error?: string | null;
  /** Дев-стенд подставляет заготовки сам — ходить в API оттуда некуда. */
  presets?: RulesPresetsResponse;
}

export function EntryScreen({ onCreate, onJoin, busy, error, presets: given }: EntryScreenProps) {
  const [tab, setTab] = useState<'create' | 'join'>('create');
  const [code, setCode] = useState('');
  const [presets, setPresets] = useState<RulesPresetsResponse | null>(given ?? null);
  const [useSeason, setUseSeason] = useState(true);
  const [settings, setSettings] = useState<TableRulesSettings>(FALLBACK_SETTINGS);

  // Заготовки не критичны для входа: не загрузились — форма работает на
  // запасных значениях, и стол всё равно можно собрать.
  useEffect(() => {
    if (given) return;
    getRulesPresets()
      .then((data) => {
        setPresets(data);
        if (data.season) setSettings(clampSettings(data.season.settings, data.limits));
      })
      .catch(() => setPresets(null));
  }, [given]);

  const limits = presets?.limits ?? FALLBACK_LIMITS;
  const season = presets?.season ?? null;
  const problem = settingsError(settings);

  function toggleSeason(on: boolean) {
    setUseSeason(on);
    // Вернул галочку — поля снова показывают эталон, а не то, что успели накрутить.
    if (on && season) setSettings(clampSettings(season.settings, limits));
  }

  function applyPreset(preset: RulesPreset) {
    setSettings(clampSettings(preset.settings, limits));
  }

  function create() {
    if (useSeason && season) onCreate({ rulesCode: season.code });
    else onCreate({ rules: settings });
  }

  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div>
          <div className={styles.title}>Одесский покер</div>
          <div className={styles.subtitle}>Собери стол или войди по коду друга</div>
        </div>

        <div className={styles.tabs}>
          <button type="button" className={tab === 'create' ? styles.tabActive : styles.tab} onClick={() => setTab('create')}>
            Создать
          </button>
          <button type="button" className={tab === 'join' ? styles.tabActive : styles.tab} onClick={() => setTab('join')}>
            Присоединиться
          </button>
        </div>

        <div className={styles.card}>
          {tab === 'create' ? (
            <>
              {season && (
                <label className={styles.seasonRow}>
                  <input type="checkbox" checked={useSeason} onChange={(e) => toggleSeason(e.target.checked)} />
                  <span>
                    <span className={styles.seasonName}>Играть по правилам сезона</span>
                    <span className={styles.seasonHint}>{season.name} — эталонная редакция</span>
                  </span>
                </label>
              )}

              {!useSeason && presets && presets.presets.length > 0 && (
                <div className={styles.presets}>
                  {presets.presets.map((p) => (
                    <button key={p.code} type="button" className={styles.preset} onClick={() => applyPreset(p)}>
                      {p.name}
                    </button>
                  ))}
                </div>
              )}

              <TableRulesForm value={settings} limits={limits} disabled={useSeason} onChange={setSettings} />

              <div className={styles.matchHint}>
                {problem ?? `В матче ${roundsTotal(settings, 3)}–${roundsTotal(settings, 5)} раздач — смотря сколько сядет`}
              </div>

              <button className={styles.btnWide} disabled={busy || problem !== null} onClick={create}>
                Создать стол
              </button>
            </>
          ) : (
            <>
              <input
                className={styles.input}
                placeholder="Код комнаты"
                value={code}
                maxLength={12}
                onChange={(e) => setCode(e.target.value)}
              />
              <button className={styles.btnWide} disabled={busy || !code.trim()} onClick={() => onJoin(code)}>
                Войти
              </button>
            </>
          )}
        </div>

        {error && <div className={styles.error}>{error}</div>}
      </div>
    </>
  );
}
