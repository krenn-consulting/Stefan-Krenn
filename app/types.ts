export interface Goal {
  id: string;
  title: string;
  description: string;
  deadline?: string;
  createdAt: string;
}

export interface Task {
  id: string;
  goalId: string;
  title: string;
  description: string;
  estimatedMinutes: number;
  priority: number;
  category: string;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped';
  completedAt?: string;
  dependencies?: string[];
  weekNumber?: number;
}

export interface DailySession {
  date: string;
  taskIds: string[];
  completedTaskIds: string[];
}

export interface AppState {
  goals: Goal[];
  tasks: Task[];
  sessions: DailySession[];
}
