import { useEffect, useState } from 'react'
import { getApiErrorMessage, getSystemStatus } from '../services/scanApi'

export default function SystemStatusPanel() {
  const [status, setStatus] = useState({ api: 'checking', database: 'checking', backend: 'checking' })

  useEffect(() => {
    getSystemStatus()
      .then((health) => setStatus({
        api: 'online',
        backend: health.status === 'ok' ? 'online' : 'offline',
        database: health.database === 'connected' ? 'online' : 'offline',
      }))
      .catch(() => setStatus({ api: 'offline', backend: 'offline', database: 'offline' }))
  }, [])

  return (
    <div className="system-status-panel glass-card">
      <div><p className="section-kicker">system status</p><strong>Intelligence services</strong></div>
      <div className="system-status-list">
        {Object.entries(status).map(([name, value]) => (
          <span key={name}><i className={`system-status-dot system-status-${value}`} /> {name} <b>{value === 'checking' ? 'Checking' : value === 'online' ? 'Online' : 'Offline'}</b></span>
        ))}
      </div>
    </div>
  )
}
