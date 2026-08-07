/** Axios instance with JWT auth interceptor and SSE support */

import axios from 'axios'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 300_000, // 5 min for long-running queries
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 → redirect to login
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export default client

/** SSE streaming chat */
export async function* streamChat(
  params: {
    engine: string
    message: string
    kb_id?: string
    datasource_id?: string
    conversation_id?: string
  },
): AsyncGenerator<{ type: string; data: any }> {
  const token = localStorage.getItem('access_token')
  const resp = await fetch('/api/v1/chat/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ ...params, stream: true }),
  })

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.replace('event:', '').trim()
      } else if (line.startsWith('data:')) {
        try {
          yield { type: currentEvent || 'message', data: JSON.parse(line.replace('data:', '').trim()) }
        } catch {
          // skip malformed data
        }
      }
    }
  }
}
