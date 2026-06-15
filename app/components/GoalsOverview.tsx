'use client';

import { Goal, Task } from '../types';
import ProgressRing from './ProgressRing';

interface GoalsOverviewProps {
  goals: Goal[];
  tasks: Task[];
  onEditGoals: () => void;
}

const goalColors = ['#3B82F6', '#8B5CF6', '#10B981'];

export default function GoalsOverview({ goals, tasks, onEditGoals }: GoalsOverviewProps) {
  const goalStats = goals.map((goal, idx) => {
    const goalTasks = tasks.filter(t => t.goalId === goal.id);
    const completed = goalTasks.filter(t => t.status === 'completed').length;
    const percentage = goalTasks.length > 0 ? Math.round((completed / goalTasks.length) * 100) : 0;
    return { goal, goalTasks, completed, percentage, color: goalColors[idx] };
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-700 text-sm uppercase tracking-wide">Meine Ziele</h3>
        <button
          onClick={onEditGoals}
          className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
        >
          Bearbeiten
        </button>
      </div>

      {goalStats.map(({ goal, goalTasks, completed, percentage, color }) => (
        <div key={goal.id} className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <div className="flex items-start gap-4">
            <ProgressRing percentage={percentage} size={64} strokeWidth={5} color={color} />
            <div className="flex-1 min-w-0">
              <h4 className="font-semibold text-gray-800 leading-tight">{goal.title}</h4>
              {goal.description && (
                <p className="text-sm text-gray-500 mt-0.5 line-clamp-2">{goal.description}</p>
              )}
              <p className="text-xs text-gray-400 mt-1">
                {completed}/{goalTasks.length} Aufgaben abgeschlossen
                {goal.deadline && ` · Ziel: ${new Date(goal.deadline).toLocaleDateString('de-AT')}`}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
