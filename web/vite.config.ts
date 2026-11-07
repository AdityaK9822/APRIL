import { defineConfig, type ViteDevServer } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { spawn } from 'node:child_process'

const root = path.resolve(__dirname, '..')
const backendPython = path.join(root, '.venv', 'bin', 'python')

const aprilBackendPlugin = () => {
  let backendProcess: ReturnType<typeof spawn> | null = null

  const startBackend = () => {
    if (backendProcess) return
    backendProcess = spawn(backendPython, ['-m', 'core.api'], {
      cwd: root,
      stdio: 'inherit',
      env: process.env,
    })
    backendProcess.on('error', (error) => {
      console.error('[APRIL backend] failed to start:', error)
    })
    backendProcess.on('exit', (code, signal) => {
      console.log('[APRIL backend] exited', code ?? signal)
      backendProcess = null
    })
  }

  const stopBackend = () => {
    if (!backendProcess) return
    backendProcess.kill('SIGTERM')
    backendProcess = null
  }

  process.on('SIGINT', stopBackend)
  process.on('SIGTERM', stopBackend)
  process.on('exit', stopBackend)

  return {
    name: 'april-backend',
    configureServer(server: ViteDevServer) {
      server.httpServer?.once('listening', () => {
        console.log('[APRIL backend] starting with frontend...')
        startBackend()
      })
      server.httpServer?.on('close', stopBackend)
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), aprilBackendPlugin()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/healthz': 'http://127.0.0.1:8000',
    },
  },
})