import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { Goal, Task } from '../../types';

const client = new Anthropic();

export async function POST(request: NextRequest) {
  const { goals } = await request.json() as { goals: Goal[] };

  const encoder = new TextEncoder();
  const stream = new TransformStream();
  const writer = stream.writable.getWriter();

  async function generate() {
    try {
      const goalsList = goals.map((g, i) =>
        `Goal ${i + 1}: ${g.title}\nDescription: ${g.description}${g.deadline ? `\nDeadline: ${g.deadline}` : ''}`
      ).join('\n\n');

      const response = await client.messages.create({
        model: 'claude-opus-4-8',
        max_tokens: 8000,
        thinking: { type: 'adaptive' },
        stream: true,
        messages: [
          {
            role: 'user',
            content: `You are a productivity and project planning expert. Create a comprehensive task plan for these goals:

${goalsList}

Generate a detailed list of tasks for each goal. For each task provide:
- A clear, actionable title
- A brief description of what needs to be done
- Estimated time in minutes (15, 30, 45, or 60 minutes)
- Priority (1=highest, 10=lowest)
- Category (research, planning, action, review, learning, networking, creation)
- Week number when this task should ideally be completed (1-12)

Output ONLY valid JSON in this exact format, no other text:
{
  "tasks": [
    {
      "goalId": "<goal_id>",
      "title": "Task title",
      "description": "What to do in this task",
      "estimatedMinutes": 30,
      "priority": 1,
      "category": "action",
      "weekNumber": 1
    }
  ]
}

Goal IDs are: ${goals.map(g => `${g.title}: "${g.id}"`).join(', ')}

Create 8-15 tasks per goal, ordered from most urgent/foundational to later tasks. Make tasks specific and achievable in the estimated time.`
          }
        ]
      });

      let fullText = '';
      for await (const event of response) {
        if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
          fullText += event.delta.text;
        }
      }

      // Parse the JSON response
      const jsonMatch = fullText.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw new Error('No JSON found in response');

      const parsed = JSON.parse(jsonMatch[0]) as { tasks: Omit<Task, 'id' | 'status'>[] };

      const tasks: Task[] = parsed.tasks.map((t) => ({
        ...t,
        id: crypto.randomUUID(),
        status: 'pending' as const,
      }));

      await writer.write(encoder.encode(JSON.stringify({ tasks })));
    } catch (error) {
      await writer.write(encoder.encode(JSON.stringify({ error: String(error) })));
    } finally {
      await writer.close();
    }
  }

  generate();

  return new NextResponse(stream.readable, {
    headers: { 'Content-Type': 'application/json' },
  });
}
