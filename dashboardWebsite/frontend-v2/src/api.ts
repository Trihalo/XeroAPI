import axios from 'axios'

const API_BASE_URL =
  import.meta.env.MODE === 'development'
    ? 'http://localhost:8080'
    : import.meta.env.VITE_API_URL

export interface AuthUser {
  name: string
  email: string
  username: string
}

export interface ApiResponse {
  success: boolean
  message: string
}

export interface AuthResponse {
  success: boolean
  message: string
  user?: AuthUser
}

export interface HistoryEntry {
  workflow: string
  called_at: unknown
  name: unknown
  success: string | number
}

export const triggerWorkflow = async (
  workflowKey: string,
  authUser: AuthUser
): Promise<ApiResponse> => {
  try {
    const response = await axios.post(`${API_BASE_URL}/trigger/${workflowKey}`, {
      user: authUser,
    })
    if (response.data.success) {
      return { success: true, message: response.data.message }
    }
    return { success: false, message: String(response.data.error ?? 'Unknown error') }
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const backendData = error.response?.data as Record<string, unknown> | undefined
      if (backendData?.error) return { success: false, message: String(backendData.error) }
      return { success: false, message: `Server error: ${error.response?.status ?? 'unknown'}` }
    }
    return { success: false, message: 'Error contacting the backend.' }
  }
}

export const uploadFile = async (file: File, targetPath?: string): Promise<ApiResponse> => {
  const formData = new FormData()
  formData.append('file', file)
  if (targetPath) formData.append('target_path', targetPath)
  try {
    const response = await axios.post(`${API_BASE_URL}/upload-file`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data as ApiResponse
  } catch {
    return { success: false, message: 'Upload failed.' }
  }
}

export interface FileInfo {
  path: string
  last_updated_at: string | null
  last_updated_by: string | null
}

export const fetchFileInfo = async (repoPath: string): Promise<FileInfo> => {
  const response = await fetch(`${API_BASE_URL}/file-info?path=${encodeURIComponent(repoPath)}`)
  return response.json() as Promise<FileInfo>
}

export const authenticateUser = async (
  username: string,
  password: string
): Promise<AuthResponse> => {
  try {
    const response = await fetch(`${API_BASE_URL}/authenticate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    const data = (await response.json()) as AuthResponse
    if (!response.ok) return { success: false, message: data.message ?? 'Authentication failed' }
    return { success: data.success, message: data.message, user: data.user }
  } catch {
    return { success: false, message: 'Authentication request failed.' }
  }
}

export const fetchHistory = async (): Promise<HistoryEntry[]> => {
  const response = await fetch(`${API_BASE_URL}/history`)
  return response.json() as Promise<HistoryEntry[]>
}

export interface WorkflowStep {
  name: string
  status: 'queued' | 'in_progress' | 'completed'
  conclusion: 'success' | 'failure' | 'skipped' | 'cancelled' | null
}

export interface RunStatus {
  run_id?: number
  status: 'queued' | 'in_progress' | 'completed' | 'not_found' | 'error'
  conclusion?: 'success' | 'failure' | 'cancelled' | 'timed_out' | null
  html_url?: string
  steps: WorkflowStep[]
}

export const fetchRunStatus = async (
  workflowFile: string,
  after: string
): Promise<RunStatus> => {
  const url = `${API_BASE_URL}/run-status?workflow=${encodeURIComponent(workflowFile)}&after=${encodeURIComponent(after)}`
  const response = await fetch(url)
  return response.json() as Promise<RunStatus>
}

export interface SummaryEntry {
  run_id: number
  run_number: number
  workflow_file: string
  summary: string
  stored_at: unknown
}

export const fetchSummaries = async (): Promise<SummaryEntry[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/summaries`)
    return response.json() as Promise<SummaryEntry[]>
  } catch {
    return []
  }
}
