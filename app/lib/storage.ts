import { AppState, Goal, Task, DailySession } from '../types';

const STORAGE_KEY = 'goal-planner-state';

export function loadState(): AppState {
  if (typeof window === 'undefined') return { goals: [], tasks: [], sessions: [] };
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { goals: [], tasks: [], sessions: [] };
    return JSON.parse(raw) as AppState;
  } catch {
    return { goals: [], tasks: [], sessions: [] };
  }
}

export function saveState(state: AppState): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function getGoals(): Goal[] {
  return loadState().goals;
}

export function getTasks(): Task[] {
  return loadState().tasks;
}

export function getTodaySession(): DailySession | undefined {
  const today = new Date().toISOString().split('T')[0];
  return loadState().sessions.find(s => s.date === today);
}

export function updateTask(taskId: string, updates: Partial<Task>): void {
  const state = loadState();
  state.tasks = state.tasks.map(t => t.id === taskId ? { ...t, ...updates } : t);
  saveState(state);
}

export function saveTodaySession(session: DailySession): void {
  const state = loadState();
  const idx = state.sessions.findIndex(s => s.date === session.date);
  if (idx >= 0) {
    state.sessions[idx] = session;
  } else {
    state.sessions.push(session);
  }
  saveState(state);
}

export function clearAll(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_KEY);
}
