'use client';

import { Task, Goal } from '../types';

const categoryColors: Record<string, string> = {
  research: 'bg-purple-100 text-purple-700',
  planning: 'bg-blue-100 text-blue-700',
  action: 'bg-green-100 text-green-700',
  review: 'bg-yellow-100 text-yellow-700',
  learning: 'bg-indigo-100 text-indigo-700',
  networking: 'bg-pink-100 text-pink-700',
  creation: 'bg-orange-100 text-orange-700',
};

interface TaskCardProps {
  task: Task;
  goal?: Goal;
  onComplete: (taskId: string) => void;
  onSkip: (taskId: string) => void;
}

export default function TaskCard({ task, goal, onComplete, onSkip }: TaskCardProps) {
  const isDone = task.status === 'completed';
  const isSkipped = task.status === 'skipped';
  const categoryColor = categoryColors[task.category] ?? 'bg-gray-100 text-gray-700';

  return (
    <div className={`bg-white rounded-2xl p-5 shadow-sm border transition-all ${
      isDone ? 'border-green-200 opacity-75' : isSkipped ? 'border-gray-100 opacity-50' : 'border-gray-100'
    }`}>
      <div className="flex items-start gap-4">
        <button
          onClick={() => !isDone && !isSkipped && onComplete(task.id)}
          className={`mt-0.5 w-6 h-6 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-all ${
            isDone
              ? 'bg-green-500 border-green-500'
              : 'border-gray-300 hover:border-green-400'
          }`}
        >
          {isDone && (
            <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          )}
        </button>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${categoryColor}`}>
              {task.category}
            </span>
            {goal && (
              <span className="text-xs text-gray-400 truncate">{goal.title}</span>
            )}
          </div>
          <h4 className={`font-semibold text-gray-800 ${isDone ? 'line-through text-gray-400' : ''}`}>
            {task.title}
          </h4>
          <p className="text-sm text-gray-500 mt-1">{task.description}</p>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {task.estimatedMinutes} Min.
            </span>
          </div>
        </div>

        {!isDone && !isSkipped && (
          <button
            onClick={() => onSkip(task.id)}
            className="text-gray-300 hover:text-gray-500 transition-colors text-xs flex-shrink-0 mt-1"
            title="Überspringen"
          >
            Überspr.
          </button>
        )}
      </div>
    </div>
  );
}
