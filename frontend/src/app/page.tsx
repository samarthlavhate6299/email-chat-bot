"use client"

import { useState } from "react"
import Link from "next/link"
import "./page.css"

export default function LandingPage() {
  const [showNotification, setShowNotification] = useState(true)

  return (<>
    <main className="hero-section">
    <h2 className="hero-title">Your Email Experience, Reimagined</h2>
    <p className="hero-description">
      Experience email management like never before. Read, draft, and handle attachments with powerful features
      designed for modern communication.
    </p>
  </main>

  {showNotification && (
    <div className="notification">
      <div className="notification-icon">N</div>
      <span className="notification-text">3 issues</span>
      <button className="close-btn" onClick={() => setShowNotification(false)}>
        ×
      </button>
    </div>
  )}
  </>
  )
}
