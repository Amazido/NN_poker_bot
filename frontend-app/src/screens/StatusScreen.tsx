import { AppHeader } from '../components/AppHeader';
import styles from './StatusScreen.module.css';

export function StatusScreen({ message, action }: { message: string; action?: { label: string; onClick: () => void } }) {
  return (
    <>
      <AppHeader roomCode="—" />
      <div className={styles.body}>
        <div className={styles.message}>{message}</div>
        {action && (
          <button className={styles.btn} onClick={action.onClick}>
            {action.label}
          </button>
        )}
      </div>
    </>
  );
}
