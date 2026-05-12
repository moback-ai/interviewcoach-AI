import React from 'react';

function ShowcasePanel({ variant }) {
  if (variant === 'login') {
    return (
      <div className="auth-briefcase-panel-shell auth-briefcase-panel-shell-login">
        <div className="auth-briefcase-panel auth-briefcase-panel-login">
          <div className="auth-briefcase-panel-login-screen">
            <span className="auth-briefcase-panel-kicker">Login</span>
            <div className="auth-briefcase-panel-line auth-briefcase-panel-line-login" />
            <div className="auth-briefcase-panel-line auth-briefcase-panel-line-login auth-briefcase-panel-line-short" />
            <div className="auth-briefcase-panel-button auth-briefcase-panel-button-login">Sign in</div>
          </div>
          <div className="auth-briefcase-panel-login-wedge">
            <span>WELCOME</span>
            <span>BACK</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-briefcase-panel-shell auth-briefcase-panel-shell-signup">
      <div className="auth-briefcase-panel auth-briefcase-panel-signup">
        <span className="auth-briefcase-panel-title">Register now</span>
        <span className="auth-briefcase-panel-caption">Save your spot in our upcoming live webinar</span>
        <div className="auth-briefcase-form-row auth-briefcase-form-row-half">
          <div className="auth-briefcase-panel-line auth-briefcase-panel-line-light">Name</div>
          <div className="auth-briefcase-panel-line auth-briefcase-panel-line-light">Surname</div>
        </div>
        <div className="auth-briefcase-panel-line auth-briefcase-panel-line-light">Enter your email address</div>
        <div className="auth-briefcase-panel-line auth-briefcase-panel-line-light">Create your password</div>
        <div className="auth-briefcase-panel-button auth-briefcase-panel-button-signup">Register</div>
      </div>
    </div>
  );
}

function BusinessAvatar() {
  return (
    <svg viewBox="0 0 240 360" className="auth-briefcase-avatar-svg" role="presentation">
      <defs>
        <linearGradient id="authBriefcaseSuit" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#d7dee9" />
          <stop offset="100%" stopColor="#aeb8c8" />
        </linearGradient>
        <linearGradient id="authBriefcaseTie" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1d4ed8" />
          <stop offset="100%" stopColor="#0f2e83" />
        </linearGradient>
        <linearGradient id="authBriefcaseHair" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7c4a27" />
          <stop offset="100%" stopColor="#4b2a16" />
        </linearGradient>
      </defs>

      <ellipse cx="120" cy="338" rx="58" ry="14" fill="rgba(10, 19, 43, 0.16)" />
      <g className="auth-briefcase-avatar-motion">
        <path d="M140 72c14 0 28 13 28 31 0 12-4 23-11 29-9 9-25 10-37 2-8-6-13-17-13-31 0-18 15-31 33-31Z" fill="#efc8a3" />
        <path d="M108 92c3-24 18-36 39-36 17 0 31 10 36 27 2 7 2 14 0 20-6-6-15-10-28-10-22 0-36 10-49 25-3-7-3-16 2-26Z" fill="url(#authBriefcaseHair)" />
        <path d="M124 86c4 0 7 3 7 7s-3 7-7 7-7-3-7-7 3-7 7-7Z" fill="#efc8a3" />
        <circle cx="130" cy="95" r="2.8" fill="#1f2937" />
        <circle cx="152" cy="95" r="2.8" fill="#1f2937" />
        <path d="M136 109c5 4 12 4 17 0" stroke="#a35f2a" strokeWidth="3" strokeLinecap="round" fill="none" />

        <path d="M92 162c10-28 28-43 52-43 25 0 43 12 56 35l-17 98h-82l-9-90Z" fill="url(#authBriefcaseSuit)" />
        <path d="M132 120h18l16 27-16 19-16-19Z" fill="#ffffff" />
        <path d="M134 120h13l8 46-14 76-15-76Z" fill="url(#authBriefcaseTie)" />
        <path d="M91 166c-11 15-18 27-20 39-2 14 7 22 19 22 10 0 18-8 18-20 0-11-5-24-17-41Z" fill="url(#authBriefcaseSuit)" />
        <path d="M200 163c9 10 13 22 13 35 0 12-7 20-18 20-10 0-17-8-17-19 0-11 5-23 16-36Z" fill="url(#authBriefcaseSuit)" />
        <ellipse cx="74" cy="220" rx="14" ry="12" fill="#efc8a3" />
        <ellipse cx="194" cy="214" rx="13" ry="11" fill="#efc8a3" />

        <path d="M118 252h21l2 68h-24Z" fill="#192233" />
        <path d="M145 252h23l17 68h-25Z" fill="#101827" />
        <path d="M112 318h34c8 0 12 5 12 12v4h-48v-4c0-7 5-12 10-12Z" fill="#f8fafc" />
        <path d="M154 318h40c7 0 12 5 12 12v4h-54v-4c0-7 4-12 2-12Z" fill="#f8fafc" />
      </g>
    </svg>
  );
}

export default function AuthBriefcaseShowcase({ variant = 'signup' }) {
  return (
    <div className={`auth-briefcase-showcase auth-briefcase-showcase-${variant}`} aria-hidden="true">
      <div className={`auth-briefcase-stage auth-briefcase-stage-${variant}`}>
        <div className="auth-briefcase-orb auth-briefcase-orb-a" />
        <div className="auth-briefcase-orb auth-briefcase-orb-b" />
        <div className="auth-briefcase-floor" />

        <div className="auth-briefcase-avatar">
          <BusinessAvatar />
        </div>

        <div className="auth-briefcase-bag">
          <div className="auth-briefcase-bag-handle" />
          <div className="auth-briefcase-bag-lid" />
          <div className="auth-briefcase-bag-base" />
          <div className="auth-briefcase-bag-glow" />
        </div>

        <div className="auth-briefcase-beam" />
        <ShowcasePanel variant={variant} />
      </div>
    </div>
  );
}
