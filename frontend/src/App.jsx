import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const API_URL = 'http://localhost:8000'

// Initial profiles
const initialProfiles = [
  { email: 'kritikaverma290902@gmail.com', password: 'kritika@2909', status: 'idle' },
  { email: 'devillover1225@gmail.com', password: 'Hii@2000', status: 'idle' },
]

function App() {
  const [profiles, setProfiles] = useState(initialProfiles)
  const [logs, setLogs] = useState([])
  const [stats, setStats] = useState({ likes: 0, videos: 0, scrolls: 0 })
  const [isRunning, setIsRunning] = useState(false)
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const wsRef = useRef(null)
  const logsEndRef = useRef(null)

  // Connect to WebSocket
  useEffect(() => {
    connectWebSocket()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const connectWebSocket = () => {
    wsRef.current = new WebSocket('ws://localhost:8000/ws')

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    }

    wsRef.current.onclose = () => {
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000)
    }
  }

  const handleWebSocketMessage = (data) => {
    // Add to logs
    addLog(data.message, data.type, data.profile)

    // Update profile status
    if (data.profile) {
      setProfiles(prev => prev.map(p =>
        p.email === data.profile
          ? { ...p, status: data.status }
          : p
      ))
    }

    // Update stats if completed
    if (data.stats) {
      setStats({
        likes: data.stats.likes || 0,
        videos: data.stats.videos_watched || 0,
        scrolls: data.stats.scroll_count || 0,
      })
    }

    // Check if all done
    if (data.type === 'complete' || data.type === 'error') {
      const allDone = profiles.every(p =>
        p.status === 'completed' || p.status === 'error' || p.status === 'idle'
      )
      if (allDone) setIsRunning(false)
    }
  }

  const addLog = (message, type = 'info', profile = null) => {
    const icons = {
      status: '🔄',
      complete: '✅',
      error: '❌',
      info: '📢',
    }

    setLogs(prev => [...prev.slice(-50), {
      id: Date.now(),
      message,
      type,
      profile,
      time: new Date().toLocaleTimeString(),
      icon: icons[type] || '📢'
    }])
  }

  const startWarmup = async (profile) => {
    try {
      const response = await fetch(`${API_URL}/warmup/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: profile.email, password: profile.password })
      })

      if (response.ok) {
        setProfiles(prev => prev.map(p =>
          p.email === profile.email ? { ...p, status: 'starting' } : p
        ))
        setIsRunning(true)
      }
    } catch (error) {
      addLog(`Failed to start: ${error.message}`, 'error', profile.email)
    }
  }

  const startAllWarmups = async () => {
    setIsRunning(true)
    for (const profile of profiles) {
      await startWarmup(profile)
      // Wait 5 seconds between starting each profile
      await new Promise(r => setTimeout(r, 5000))
    }
  }

  const addProfile = () => {
    if (newEmail && newPassword) {
      setProfiles(prev => [...prev, {
        email: newEmail,
        password: newPassword,
        status: 'idle'
      }])
      setNewEmail('')
      setNewPassword('')
    }
  }

  const removeProfile = (email) => {
    setProfiles(prev => prev.filter(p => p.email !== email))
  }

  const getStatusBadge = (status) => {
    const statusMap = {
      idle: { label: 'Ready', class: 'idle' },
      starting: { label: 'Starting...', class: 'running' },
      browser_ready: { label: 'Browser Ready', class: 'running' },
      logging_in: { label: 'Logging In', class: 'running' },
      logged_in: { label: 'Logged In', class: 'running' },
      warming_up: { label: 'Warming Up', class: 'running' },
      completed: { label: 'Completed', class: 'completed' },
      error: { label: 'Error', class: 'error' },
      login_failed: { label: 'Login Failed', class: 'error' },
    }
    return statusMap[status] || { label: status, class: 'idle' }
  }

  return (
    <div className="app">
      {/* Background orbs */}
      <div className="bg-orb bg-orb-1" />
      <div className="bg-orb bg-orb-2" />
      <div className="bg-orb bg-orb-3" />

      {/* Header */}
      <motion.header
        className="header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1>Profile Warm-Up</h1>
        <p>Automated Facebook profile warming with human-like behavior</p>
      </motion.header>

      <div className="container">
        {/* Profiles Card */}
        <motion.div
          className="card"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
        >
          <h2 className="card-title">
            <span>👥</span> Profiles
          </h2>

          <div className="profiles-list">
            <AnimatePresence>
              {profiles.map((profile, index) => {
                const badge = getStatusBadge(profile.status)
                return (
                  <motion.div
                    key={profile.email}
                    className="profile-card"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <div className="profile-info">
                      <div className={`profile-avatar p${(index % 4) + 1}`}>
                        {profile.email[0].toUpperCase()}
                      </div>
                      <div>
                        <div className="profile-email">{profile.email}</div>
                        <div className="profile-status">
                          <span className={`status-badge ${badge.class}`}>
                            {badge.label}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <motion.button
                        className="btn btn-primary"
                        onClick={() => startWarmup(profile)}
                        disabled={isRunning || profile.status !== 'idle'}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        Start
                      </motion.button>
                      <motion.button
                        className="btn"
                        onClick={() => removeProfile(profile.email)}
                        style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                      >
                        ✕
                      </motion.button>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>

          <motion.button
            className="btn btn-start-all"
            onClick={startAllWarmups}
            disabled={isRunning}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isRunning ? '🔄 Running...' : '🚀 Start All Warm-Ups'}
          </motion.button>

          {/* Add profile form */}
          <div className="add-profile-form">
            <div className="input-group">
              <label>Email</label>
              <input
                type="email"
                placeholder="Enter email..."
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
              />
            </div>
            <div className="input-group">
              <label>Password</label>
              <input
                type="password"
                placeholder="Enter password..."
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <motion.button
              className="btn btn-primary"
              onClick={addProfile}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              ➕ Add Profile
            </motion.button>
          </div>
        </motion.div>

        {/* Activity & Stats Card */}
        <motion.div
          className="card"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2 }}
        >
          <h2 className="card-title">
            <span>📊</span> Activity
          </h2>

          {/* Stats Grid */}
          <div className="stats-grid">
            <motion.div
              className="stat-card"
              whileHover={{ scale: 1.05 }}
            >
              <div className="stat-value">{stats.likes}</div>
              <div className="stat-label">Likes</div>
            </motion.div>
            <motion.div
              className="stat-card"
              whileHover={{ scale: 1.05 }}
            >
              <div className="stat-value">{stats.videos}</div>
              <div className="stat-label">Videos Watched</div>
            </motion.div>
            <motion.div
              className="stat-card"
              whileHover={{ scale: 1.05 }}
            >
              <div className="stat-value">{stats.scrolls}</div>
              <div className="stat-label">Scrolls</div>
            </motion.div>
            <motion.div
              className="stat-card"
              whileHover={{ scale: 1.05 }}
            >
              <div className="stat-value">{profiles.filter(p => p.status === 'completed').length}</div>
              <div className="stat-label">Completed</div>
            </motion.div>
          </div>

          {/* Activity Log */}
          <h3 style={{ marginTop: '1.5rem', marginBottom: '1rem', fontSize: '1.1rem' }}>
            Live Activity
          </h3>
          <div className="activity-log">
            <AnimatePresence>
              {logs.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '2rem',
                  color: 'rgba(255,255,255,0.4)'
                }}>
                  No activity yet. Start a warm-up to see logs here.
                </div>
              ) : (
                logs.map((log) => (
                  <motion.div
                    key={log.id}
                    className="log-item"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                  >
                    <div className={`log-icon ${log.type}`}>
                      {log.icon}
                    </div>
                    <div className="log-content">
                      <div className="log-message">{log.message}</div>
                      <div className="log-time">
                        {log.profile && <span>{log.profile.split('@')[0]} • </span>}
                        {log.time}
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
        </motion.div>
      </div>
    </div>
  )
}

export default App
