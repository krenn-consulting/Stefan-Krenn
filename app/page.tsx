'use client';

import { useState, useEffect, useCallback } from 'react';
import { Goal, Task, AppState } from './types';
import { loadState, saveState } from './lib/storage';
import GoalForm from './components/GoalForm';
import DailySession from './components/DailySession';
import GoalsOverview from './components/GoalsOverview';

type View = 'setup' | 'generating' | 'dashboard';

export default function Home() {
  const [state, setState] = useState<AppState>({ goals: [], tasks: [], sessions: [] });
  const [view, setView] = useState<View>('setup');
  const [generatingStatus, setGeneratingStatus] = useState('');
  const [activeTab, setActiveTab] = useState<'session' | 'goals'>('session');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const loaded = loadState();
    setState(loaded);
    if (loaded.goals.length > 0 && loaded.tasks.length > 0) {
      setView('dashboard');
    }
    setMounted(true);
  }, []);

  const refreshState = useCallback(() => {
    setState(loadState());
  }, []);

  async function handleGoalsSaved(goals: Goal[]) {
    setView('generating');
    setGeneratingStatus('Analysiere deine Ziele...');

    try {
      const res = await fetch('/api/generate-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goals }),
      });

      setGeneratingStatus('KI erstellt deinen persönlichen Plan...');

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let raw = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        raw += decoder.decode(value, { stream: true });
      }

      const data = JSON.parse(raw) as { tasks?: Task[]; error?: string };

      if (data.error) throw new Error(data.error);
      if (!data.tasks) throw new Error('No tasks returned');

      const newState: AppState = {
        goals,
        tasks: data.tasks,
        sessions: [],
      };
      saveState(newState);
      setState(newState);
      setView('dashboard');
    } catch (err) {
      console.error(err);
      setGeneratingStatus('Fehler beim Erstellen des Plans. Bitte versuche es erneut.');
      setTimeout(() => setView('setup'), 3000);
    }
  }

  function handleEditGoals() {
    setView('setup');
  }

  function handleReset() {
    if (confirm('Alle Ziele und Aufgaben löschen?')) {
      const empty: AppState = { goals: [], tasks: [], sessions: [] };
      saveState(empty);
      setState(empty);
      setView('setup');
    }
  }

  if (!mounted) return null;

  if (view === 'setup') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <div className="max-w-lg mx-auto w-full px-4 py-8 flex-1">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Ziele erreichen</h1>
            <p className="text-gray-500">Gib 1–3 Ziele ein. Die KI erstellt deinen persönlichen Aktionsplan.</p>
          </div>
          <GoalForm onSave={handleGoalsSaved} existingGoals={state.goals} />
        </div>
      </div>
    );
  }

  if (view === 'generating') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-6 px-4">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">Plan wird erstellt</h2>
            <p className="text-gray-500">{generatingStatus}</p>
          </div>
          <p className="text-sm text-gray-400 max-w-xs mx-auto">
            Die KI analysiert deine Ziele und erstellt einen maßgeschneiderten Plan mit allen nötigen Aufgaben.
          </p>
        </div>
      </div>
    );
  }

  const pendingCount = state.tasks.filter(t => t.status === 'pending').length;
  const completedCount = state.tasks.filter(t => t.status === 'completed').length;

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="font-bold text-gray-900">Ziele erreichen</h1>
            <p className="text-xs text-gray-400">{completedCount}/{state.tasks.length} Aufgaben erledigt</p>
          </div>
          <button
            onClick={handleReset}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors px-2 py-1"
          >
            Zurücksetzen
          </button>
        </div>
      </header>

      <div className="max-w-lg mx-auto w-full px-4 pt-4">
        <div className="bg-gray-100 rounded-xl p-1 flex">
          <button
            onClick={() => setActiveTab('session')}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              activeTab === 'session' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
            }`}
          >
            Heute
          </button>
          <button
            onClick={() => setActiveTab('goals')}
            className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all ${
              activeTab === 'goals' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
            }`}
          >
            Ziele
          </button>
        </div>
      </div>

      <main className="max-w-lg mx-auto w-full px-4 py-4 flex-1">
        {activeTab === 'session' ? (
          <DailySession
            goals={state.goals}
            tasks={state.tasks}
            onTasksChange={refreshState}
          />
        ) : (
          <GoalsOverview
            goals={state.goals}
            tasks={state.tasks}
            onEditGoals={handleEditGoals}
          />
        )}
      </main>

      <div className="bg-white border-t border-gray-100 py-3">
        <div className="max-w-lg mx-auto px-4 flex justify-around text-center">
          <div>
            <div className="text-lg font-bold text-gray-900">{state.goals.length}</div>
            <div className="text-xs text-gray-400">Ziele</div>
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">{pendingCount}</div>
            <div className="text-xs text-gray-400">Offen</div>
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">{completedCount}</div>
            <div className="text-xs text-gray-400">Erledigt</div>
          </div>
        </div>
      </div>
    </div>
  );
}
