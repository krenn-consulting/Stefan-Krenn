'use client';

import { useState } from 'react';
import { Goal } from '../types';

interface GoalFormProps {
  onSave: (goals: Goal[]) => void;
  existingGoals?: Goal[];
}

const emptyGoal = () => ({ title: '', description: '', deadline: '' });

export default function GoalForm({ onSave, existingGoals }: GoalFormProps) {
  const [goals, setGoals] = useState(
    existingGoals && existingGoals.length > 0
      ? existingGoals.map(g => ({ title: g.title, description: g.description, deadline: g.deadline || '' }))
      : [emptyGoal()]
  );

  const addGoal = () => {
    if (goals.length < 3) setGoals([...goals, emptyGoal()]);
  };

  const removeGoal = (idx: number) => {
    setGoals(goals.filter((_, i) => i !== idx));
  };

  const update = (idx: number, field: string, value: string) => {
    setGoals(goals.map((g, i) => i === idx ? { ...g, [field]: value } : g));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validGoals = goals.filter(g => g.title.trim());
    if (validGoals.length === 0) return;

    const existingMap = new Map(existingGoals?.map(g => [g.title, g]) ?? []);
    const saved: Goal[] = validGoals.map(g => {
      const existing = existingMap.get(g.title);
      return {
        id: existing?.id ?? crypto.randomUUID(),
        title: g.title.trim(),
        description: g.description.trim(),
        deadline: g.deadline || undefined,
        createdAt: existing?.createdAt ?? new Date().toISOString(),
      };
    });
    onSave(saved);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {goals.map((goal, idx) => (
        <div key={idx} className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800">Ziel {idx + 1}</h3>
            {goals.length > 1 && (
              <button
                type="button"
                onClick={() => removeGoal(idx)}
                className="text-gray-400 hover:text-red-500 transition-colors text-sm"
              >
                Entfernen
              </button>
            )}
          </div>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Ziel (z.B. Ich laufe einen Marathon)"
              value={goal.title}
              onChange={e => update(idx, 'title', e.target.value)}
              required
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-800 placeholder-gray-400"
            />
            <textarea
              placeholder="Beschreibung (optional — was bedeutet dieses Ziel für dich?)"
              value={goal.description}
              onChange={e => update(idx, 'description', e.target.value)}
              rows={2}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-800 placeholder-gray-400 resize-none"
            />
            <input
              type="date"
              placeholder="Deadline (optional)"
              value={goal.deadline}
              onChange={e => update(idx, 'deadline', e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-600"
            />
          </div>
        </div>
      ))}

      {goals.length < 3 && (
        <button
          type="button"
          onClick={addGoal}
          className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-500 transition-colors font-medium"
        >
          + Weiteres Ziel hinzufügen
        </button>
      )}

      <button
        type="submit"
        className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold text-lg transition-colors shadow-sm"
      >
        Plan erstellen →
      </button>
    </form>
  );
}
