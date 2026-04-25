const API_BASE = "http://localhost:8000/api";

export interface Step {
  stage: string;
  status: "pending" | "running" | "completed" | "failed";
  inputs: any;
  outputs?: any;
  session_id?: string;
  error?: string;
}

export interface Task {
  id: string;
  title?: string;
  phenomenon: string;
  env_folder: string;
  framework: string;
  model?: string;
  db_path: string;
  status: "pending" | "running" | "completed" | "failed" | "paused";
  current_stage?: string;
  steps: Step[];
  workflow_name: string;
  workflow_structure: any[];
}

export async function listTasks(): Promise<Task[]> {
  const res = await fetch(`${API_BASE}/tasks`);
  return res.json();
}

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${id}`);
  return res.json();
}

export async function createTask(data: {
  phenomenon: string;
  env_folder: string;
  framework: string;
  model?: string;
}): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to create task");
  }
  return res.json();
}

export async function cancelTask(id: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${id}/cancel`, { method: "POST" });
}

export async function resumeTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${id}/resume`, { method: "POST" });
  return res.json();
}

export async function deleteTask(id: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${id}`, { method: "DELETE" });
}
