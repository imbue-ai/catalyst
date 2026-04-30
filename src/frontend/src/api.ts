export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const API_BASE = `${API_BASE_URL}/api`;

export interface Step {
  stage: string;
  status: "pending" | "running" | "completed" | "failed" | "paused" | "canceled";
  inputs: any;
  outputs?: any;
  session_id?: string;
  last_status?: string;
  error?: string;
}

export interface Addon {
  type: string;
  theory_id: string;
  direction?: string;
  max_refinements?: number;
  apply_extensions?: boolean;
  evolve_iterations?: number;
  num_parents?: number;
  streamline_prob?: number;
  num_extra_scores?: number;
}

export interface Task {
  id: string;
  title?: string;
  workflow_inputs: any;
  env_folder: string;
  framework: string;
  model?: string;
  status: "pending" | "running" | "completed" | "failed" | "paused";
  current_stage?: string;
  steps: Step[];
  addons: Addon[];
  workflow_name: string;
  workflow_structure: any[];
  created_at?: string;
}

export interface TheoryArtifact {
  id: string;
  agent_type: string;
  category: string;
  created_at: string;
  parent_theory: string | null;
  extra: Record<string, string>;
  score?: number | null;
}

export const getTasks = async (): Promise<Task[]> => {
  const res = await fetch(`${API_BASE}/tasks`);
  return res.json();
}

export const listTasks = async (): Promise<Task[]> => {
  const res = await fetch(`${API_BASE}/tasks`);
  return res.json();
}

export async function getTask(id: string): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${id}`);
  return res.json();
}

export async function createTask(data: {
  workflow_name: string;
  workflow_inputs: any;
  template_folder?: string;
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

export async function createAddon(taskId: string, addon: Omit<Addon, 'id'>): Promise<Task> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/addons`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(addon),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to add addon");
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

export async function getTheories(id: string): Promise<TheoryArtifact[]> {
  const res = await fetch(`${API_BASE}/tasks/${id}/theories`);
  if (!res.ok) throw new Error("Failed to get theories");
  return res.json();
}

export async function getTemplates(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/templates`);
  if (!res.ok) throw new Error("Failed to get templates");
  return res.json();
}

export async function exportArtifact(taskId: string, artifactId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/artifacts/${artifactId}/export`);
  if (!res.ok) throw new Error("Failed to export artifact");
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${artifactId}.zip`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function cancelStep(taskId: string, stage: string): Promise<void> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/steps/${stage}/cancel`, { method: "POST" });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to cancel step");
  }
}

export async function bulkCancelSteps(taskId: string, stages: string[]): Promise<void> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/steps/bulk-cancel`, { 
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stages })
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to cancel steps");
  }
}

export async function deleteTask(id: string): Promise<void> {
  await fetch(`${API_BASE}/tasks/${id}`, { method: "DELETE" });
}
