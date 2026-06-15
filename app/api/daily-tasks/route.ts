import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { Goal, Task } from '../../types';

const client = new Anthropic();

export async function POST(request: NextRequest) {
  const { goals, tasks, completedTaskIds } = await request.json() as {
    goals: Goal[];
    tasks: Task[];
    completedTaskIds: string[];
  };

  const pendingTasks = tasks.filter(t => t.status === 'pending' || t.status === 'in_progress');

  if (pendingTasks.length === 0) {
    return NextResponse.json({ taskIds: [] });
  }

  const goalProgress = goals.map(goal => {
    const goalTasks = tasks.filter(t => t.goalId === goal.id);
    const completed = goalTasks.filter(t => t.status === 'completed').length;
    return {
      goal: goal.title,
      total: goalTasks.length,
      completed,
      percentage: goalTasks.length > 0 ? Math.round((completed / goalTasks.length) * 100) : 0,
    };
  });

  const taskSummary = pendingTasks.slice(0, 30).map(t => ({
    id: t.id,
    title: t.title,
    goalId: t.goalId,
    estimatedMinutes: t.estimatedMinutes,
    priority: t.priority,
    category: t.category,
    weekNumber: t.weekNumber,
  }));

  try {
    const response = await client.messages.create({
      model: 'claude-opus-4-8',
      max_tokens: 2000,
      thinking: { type: 'adaptive' },
      messages: [
        {
          role: 'user',
          content: `You are a productivity expert helping someone optimize their daily 60-minute work session.

Goal progress:
${goalProgress.map(g => `- ${g.goal}: ${g.completed}/${g.total} tasks (${g.percentage}%)`).join('\n')}

Available tasks (sorted by priority):
${taskSummary.map(t => `ID: ${t.id} | "${t.title}" | ${t.estimatedMinutes}min | Priority: ${t.priority} | Category: ${t.category} | Week: ${t.weekNumber || '?'}`).join('\n')}

Select the best tasks to fill exactly 60 minutes today. Rules:
1. Prioritize tasks that move the LEAST progressed goals forward
2. Prefer high-priority (lower number) tasks
3. Mix task categories when possible for variety
4. Total time must be as close to 60 minutes as possible without exceeding it significantly (max 75 min)
5. Pick 2-4 tasks

Output ONLY valid JSON, no other text:
{"taskIds": ["id1", "id2", "id3"]}`
        }
      ]
    });

    const text = response.content.find(c => c.type === 'text')?.text || '';
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return NextResponse.json({ taskIds: pendingTasks.slice(0, 3).map(t => t.id) });

    const parsed = JSON.parse(jsonMatch[0]) as { taskIds: string[] };
    return NextResponse.json({ taskIds: parsed.taskIds });
  } catch {
    return NextResponse.json({ taskIds: pendingTasks.slice(0, 3).map(t => t.id) });
  }
}
