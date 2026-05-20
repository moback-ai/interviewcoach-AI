import React from 'react';
import StyleBackdrop from '../common/StyleBackdrop';
import { AUTH_BACKGROUND_STYLE_ID } from '../../lib/backgroundStyles';

export default function AuthStudioShell({
  eyebrow,
  title,
  description,
  wide = false,
  children,
  footer,
  heroTitle = 'Practice interviews with confidence.',
  heroCopy = 'Tailored questions from your resume and job description, plus voice-led mock sessions and instant feedback.',
}) {
  return (
    <div className="auth-studio-page">
      <StyleBackdrop
        styleId={AUTH_BACKGROUND_STYLE_ID}
        deferWaves
        interactive
        className="auth-studio-page-backdrop"
      />

      <aside className="auth-studio-hero">
        <div className="auth-studio-hero-backdrop">
          <div className="auth-studio-hero-shade" />
          <div className="auth-studio-hero-grid" />
        </div>
        <div className="auth-studio-hero-content">
          <p className="auth-studio-hero-kicker">InterviewCoach</p>
          <h2 className="auth-studio-hero-title">{heroTitle}</h2>
          <p className="auth-studio-hero-copy">{heroCopy}</p>
          <ul className="auth-studio-hero-points">
            <li>Resume-aware question sets</li>
            <li>Voice mock interviews</li>
            <li>Actionable feedback</li>
          </ul>
        </div>
      </aside>

      <div className="auth-studio-panel">
        <section className={`auth-studio-card ${wide ? 'auth-studio-card-wide' : ''}`}>
          <header className="auth-studio-header">
            {eyebrow ? <p className="auth-studio-eyebrow">{eyebrow}</p> : null}
            {title ? <h1 className="auth-studio-title">{title}</h1> : null}
            {description ? <p className="auth-studio-copy">{description}</p> : null}
          </header>
          <div className="auth-studio-content">{children}</div>
          {footer ? <div className="auth-studio-footer">{footer}</div> : null}
        </section>
      </div>
    </div>
  );
}
