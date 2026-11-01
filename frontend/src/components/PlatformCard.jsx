import { FaFacebook, FaGithub, FaInstagram, FaLinkedin, FaReddit, FaTelegram, FaYoutube } from 'react-icons/fa'
import { FaXTwitter } from 'react-icons/fa6'
import { SiThreads, SiTiktok } from 'react-icons/si'

const PLATFORM_META = {
  github: { label: 'GitHub', icon: FaGithub, color: '#6e7681', url: (username) => `https://github.com/${username}` },
  reddit: { label: 'Reddit', icon: FaReddit, color: '#FF4500', url: (username) => `https://reddit.com/u/${username}` },
  twitter: { label: 'Twitter / X', icon: FaXTwitter, color: '#ffffff', url: (username) => `https://x.com/${username}` },
  instagram: { label: 'Instagram', icon: FaInstagram, color: '#dd2a7b', gradient: 'linear-gradient(135deg, #f58529, #dd2a7b, #8134af)', url: (username) => `https://instagram.com/${username}` },
  linkedin: { label: 'LinkedIn', icon: FaLinkedin, color: '#0A66C2', url: (username) => `https://linkedin.com/in/${username}` },
  facebook: { label: 'Facebook', icon: FaFacebook, color: '#1877F2', url: (username) => `https://facebook.com/${username}` },
  youtube: { label: 'YouTube', icon: FaYoutube, color: '#FF0000', url: (username) => `https://youtube.com/@${username}` },
  tiktok: { label: 'TikTok', icon: SiTiktok, color: '#00F2EA', accent: '#FF0050', url: (username) => `https://tiktok.com/@${username}` },
  threads: { label: 'Threads', icon: SiThreads, color: '#ffffff', url: (username) => `https://threads.net/@${username}` },
  telegram: { label: 'Telegram', icon: FaTelegram, color: '#229ED9', url: (username) => `https://t.me/${username}` },
}

export default function PlatformCard({ platform, present, status, reason, username, onCopy, copied, index = 0 }) {
  const meta = PLATFORM_META[platform]
  const Icon = meta.icon
  const profileUrl = meta.url(username)
  const effectiveStatus = present || status === 'FOUND'
    ? 'FOUND'
    : status === 'UNVERIFIED'
      ? 'UNVERIFIED'
      : 'NOT_FOUND'
  const isFound = effectiveStatus === 'FOUND'
  const isUnverified = effectiveStatus === 'UNVERIFIED'

  return (
    <article
      className={`platform-card glass-card ${isFound ? 'platform-card-found' : 'platform-card-missing'}`}
      style={{ '--card-delay': `${index * 70}ms`, '--platform-color': meta.color, '--platform-accent': meta.accent ?? meta.color }}
    >
      <div className="platform-card-main">
        <div className="platform-mark" aria-hidden="true">
          <Icon />
        </div>
        <div className="min-w-0">
          <h3 className="platform-name">{meta.label}</h3>
          <p className="platform-signal">
            {isUnverified ? 'verification unavailable' : isFound ? 'public signal detected' : 'no public signal found'}
          </p>
        </div>
      </div>
      <div className="platform-card-actions">
        <span className={`status-pill ${isFound ? 'status-found' : isUnverified ? 'status-unverified' : 'status-clear'}`}>
          <span className="status-dot" /> {isUnverified ? 'Unable to verify' : isFound ? 'Found' : 'Not found'}
        </span>
        {isUnverified && <p className="verification-reason">{reason}</p>}
        {isFound && (
          <div className="profile-actions">
            <span className="verified-badge">✓ Verified</span>
            <a className="open-profile-link" href={profileUrl} target="_blank" rel="noreferrer">
              Open profile <span aria-hidden="true">↗</span>
            </a>
            <button type="button" className="copy-profile-button" onClick={() => onCopy(profileUrl, platform)}>
              {copied ? 'Copied' : 'Copy URL'}
            </button>
          </div>
        )}
      </div>
    </article>
  )
}
