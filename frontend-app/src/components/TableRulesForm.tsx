import type { RulesFormLimits, TableRulesSettings } from '../types/game';
import { clampSettings, maxPeak } from '../lib/rulesForm';
import styles from './TableRulesForm.module.css';

function NumField({
  label,
  value,
  min,
  max,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  disabled?: boolean;
  onChange: (n: number) => void;
}) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <input
        className={styles.num}
        type="number"
        inputMode="numeric"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        // Пустое поле в момент набора даёт NaN — держим прежнее значение,
        // иначе цифра стирается из-под пальцев.
        onChange={(e) => Number.isFinite(e.target.valueAsNumber) && onChange(e.target.valueAsNumber)}
      />
    </label>
  );
}

function Check({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className={styles.check}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export interface TableRulesFormProps {
  value: TableRulesSettings;
  limits: RulesFormLimits;
  disabled?: boolean;
  onChange: (next: TableRulesSettings) => void;
}

export function TableRulesForm({ value, limits, disabled, onChange }: TableRulesFormProps) {
  const top = maxPeak(value, limits);

  function set<K extends keyof TableRulesSettings>(key: K, next: TableRulesSettings[K]) {
    onChange(clampSettings({ ...value, [key]: next }, limits));
  }

  return (
    <div className={styles.form}>
      <div className={styles.group}>
        <div className={styles.groupLabel}>
          Раздачи <span className={styles.groupHint}>карт на руку, максимум {top}</span>
        </div>
        <div className={styles.row}>
          <NumField
            label="Первая"
            value={value.rounds_start}
            min={limits.min_start}
            max={top}
            disabled={disabled}
            onChange={(n) => set('rounds_start', n)}
          />
          <NumField
            label="Самая большая"
            value={value.rounds_peak}
            min={limits.min_start}
            max={top}
            disabled={disabled}
            onChange={(n) => set('rounds_peak', n)}
          />
        </div>
      </div>

      <div className={styles.group}>
        <div className={styles.groupLabel}>Старшинство</div>
        <Check
          label="Двойка бьёт туза своей масти"
          checked={value.two_beats_ace}
          disabled={disabled}
          onChange={(v) => set('two_beats_ace', v)}
        />
        <Check
          label="Некозырной джокер бьёт козырного"
          checked={value.offcolor_beats_oncolor}
          disabled={disabled}
          onChange={(v) => set('offcolor_beats_oncolor', v)}
        />
      </div>

      <div className={styles.group}>
        <div className={styles.groupLabel}>Заказ</div>
        <Check
          label="Разрешить заказ не глядя"
          checked={value.blind_allowed}
          disabled={disabled}
          onChange={(v) => set('blind_allowed', v)}
        />
        {value.blind_allowed && (
          <div className={styles.row}>
            <NumField
              label="Награда за точный заказ вслепую"
              value={value.blind_bonus}
              min={0}
              max={999}
              disabled={disabled}
              onChange={(n) => set('blind_bonus', n)}
            />
          </div>
        )}
      </div>

      <div className={styles.group}>
        <div className={styles.groupLabel}>Колода</div>
        <div className={styles.seg}>
          <button
            type="button"
            className={value.infinite_deck ? styles.segBtn : styles.segBtnActive}
            disabled={disabled}
            onClick={() => set('infinite_deck', false)}
          >
            Одна колода
          </button>
          <button
            type="button"
            className={value.infinite_deck ? styles.segBtnActive : styles.segBtn}
            disabled={disabled}
            onClick={() => set('infinite_deck', true)}
          >
            Бесконечная
          </button>
        </div>
        {value.infinite_deck && (
          <div className={styles.note}>Карты повторяются; при равных взятку берёт положивший раньше</div>
        )}
      </div>

      <div className={styles.group}>
        <div className={styles.groupLabel}>
          Очки <span className={styles.groupHint}>штрафы — положительным числом</span>
        </div>
        <div className={styles.row}>
          <NumField
            label="За пас"
            value={value.pass_reward}
            min={0}
            max={999}
            disabled={disabled}
            onChange={(n) => set('pass_reward', n)}
          />
          <NumField
            label="За каждую взятку"
            value={value.trick_reward}
            min={0}
            max={999}
            disabled={disabled}
            onChange={(n) => set('trick_reward', n)}
          />
        </div>
        <div className={styles.row}>
          <NumField
            label="Штраф за перебор"
            value={value.overtrick_penalty}
            min={0}
            max={999}
            disabled={disabled}
            onChange={(n) => set('overtrick_penalty', n)}
          />
          <NumField
            label="Штраф за недобор"
            value={value.undertrick_penalty}
            min={0}
            max={999}
            disabled={disabled}
            onChange={(n) => set('undertrick_penalty', n)}
          />
        </div>
      </div>
    </div>
  );
}
