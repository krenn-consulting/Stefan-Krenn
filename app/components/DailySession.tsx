'use client';

import { useState, useEffect } from 'react';
import { Goal, Task, DailySession as DailySessionType } from '../types';
import { loadState, updateTask, saveTodaySession, getTodaySession } from '../lib/storage';
import TaskCard from './TaskCard';

interface DailySessionProps {
  goals: Goal[];
  tasks: Task[];
  onTasksChange: () => void;
}

export default function DailySession({ goals, tasks, onTasksChange }: DailySessionProps) {
  const [session, setSession] = useState<DailySessionType | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionTasks, setSessionTasks] = useState<Task[]>([]);

  const today = new Date().toISOString().split('T')[0];

  useEffect(() => {
    const existing = getTodaySession();
    if (existing) {
      setSession(existing);
      const todayTasks = tasks.filter(t => existing.taskIds.includes(t.id));
      setSessionTasks(todayTasks);
    } else {
      loadDailyTasks();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDailyTasks() {
    setLoading(true);
    try {
      const state = loadState();
      const completedTaskIds = state.tasks.filter(t => t.status === 'completed').map(t => t.id);

      const res = await fetch('/api/daily-tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goals, tasks, completedTaskIds }),
      });
      const data = await res.json() as { taskIds: string[] };

      const newSession: DailySessionType = {
        date: today,
        taskIds: data.taskIds,
        completedTaskIds: [],
      };

      saveTodaySession(newSession);
      setSession(newSession);
      setSessionTasks(tasks.filter(t => data.taskIds.includes(t.id)));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function handleComplete(taskId: string) {
    updateTask(taskId, { status: 'completed', completedAt: new Date().toISOString() });

    if (session) {
      const updated: DailySessionType = {
        ...session,
        completedTaskIds: [...session.completedTaskIds, taskId],
      };
      saveTodaySession(updated);
      setSession(updated);
    }

    setSessionTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: 'completed' as const, completedAt: new Date().toISOString() } : t));
    onTasksChange();
  }

  function handleSkip(taskId: string) {
    updateTask(taskId, { status: 'skipped' });
    setSessionTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: 'skipped' as const } : t));
    onTasksChange();
  }

  const totalMinutes = sessionTasks.reduce((sum, t) => sum + t.estimatedMinutes, 0);
  const completedMinutes = sessionTasks.filter(t => t.status === 'completed').reduce((sum, t) => sum + t.estimatedMinutes, 0);
  const progressPercent = totalMinutes > 0 ? Math.round((completedMinutes / totalMinutes) * 100) : 0;
  const allDone = sessionTasks.length > 0 && sessionTasks.every(t => t.status === 'completed' || t.status === 'skipped');

  const goalMap = new Map(goals.map(g => [g.id, g]));

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-500">KI wählt deine besten Aufgaben für heute aus...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Session header */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-blue-200 text-sm font-medium mb-1">Heutige Session</p>
            <h2 className="text-2xl font-bold">60 Minuten Focus</h2>
            <p className="text-blue-200 mt-1">
              {completedMinutes} / {totalMinutes} Minuten erledigt
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold">{progressPercent}%</div>
            <div className="text-blue-200 text-sm">abgeschlossen</div>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-4 bg-blue-500/50 rounded-full h-2">
          <div
            className="bg-white rounded-full h-2 transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>

      {allDone ? (
        <div className="bg-green-50 rounded-2xl p-8 text-center border border-green-100">
          <div className="text-4xl mb-3">🎉</div>
          <h3 className="text-xl font-bold text-green-800 mb-2">Großartige Arbeit!</h3>
          <p className="text-green-600">Du hast deine heutige Session abgeschlossen. Komm morgen wieder!</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h3 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">Aufgaben für heute</h3>
          {sessionTasks.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              goal={goalMap.get(task.goalId)}
              onComplete={handleComplete}
              onSkip={handleSkip}
            />
          ))}
        </div>
      )}

      <button
        onClick={loadDailyTasks}
        className="w-full py-3 text-gray-500 hover:text-blue-600 text-sm transition-colors"
      >
        Neue Aufgaben laden
      </button>
    </div>
  );
}
