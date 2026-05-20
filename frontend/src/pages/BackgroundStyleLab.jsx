import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FiCheck, FiCopy, FiMonitor, FiSun } from 'react-icons/fi';
import Navbar from '../components/Navbar';
import StyleBackdrop from '../components/common/StyleBackdrop';
import { useTheme } from '../hooks/useTheme';
import {
  BACKGROUND_STYLES,
  getSelectedBackgroundStyleId,
  setSelectedBackgroundStyleId,
} from '../lib/backgroundStyles';

function MockAuthCard() {
  return (
    <section className="bg-style-lab__mock-card">
      <p className="auth-studio-eyebrow">Sign in</p>
      <h2 className="auth-studio-title">Welcome back</h2>
      <p className="auth-studio-copy">Preview how the login card reads on this background.</p>
      <div className="bg-style-lab__mock-fields" aria-hidden="true">
        <div className="bg-style-lab__mock-field" />
        <div className="bg-style-lab__mock-field" />
        <div className="bg-style-lab__mock-button">Sign in</div>
      </div>
    </section>
  );
}

function MockAppCard() {
  return (
    <section className="bg-style-lab__mock-card bg-style-lab__mock-card--app">
      <p className="auth-studio-eyebrow">Upload</p>
      <h2 className="auth-studio-title">Resume &amp; job description</h2>
      <p className="auth-studio-copy">Preview how upload and dashboard panels sit on this background.</p>
      <div className="bg-style-lab__mock-upload-grid" aria-hidden="true">
        <div className="bg-style-lab__mock-upload-tile">Resume PDF</div>
        <div className="bg-style-lab__mock-upload-tile">Job description</div>
        <div className="bg-style-lab__mock-button">Generate questions</div>
      </div>
    </section>
  );
}

export default function BackgroundStyleLab() {
  const { theme, toggleTheme } = useTheme();
  const [previewId, setPreviewId] = useState(() => getSelectedBackgroundStyleId());
  const [selectedId, setSelectedId] = useState(() => getSelectedBackgroundStyleId());
  const [previewContext, setPreviewContext] = useState('login');
  const [copied, setCopied] = useState(false);

  const previewStyle = useMemo(
    () => BACKGROUND_STYLES.find((style) => style.id === previewId) || BACKGROUND_STYLES[0],
    [previewId]
  );

  const handleSelect = useCallback((styleId) => {
    const resolved = setSelectedBackgroundStyleId(styleId);
    setSelectedId(resolved);
    setPreviewId(resolved);
  }, []);

  const handleCopy = useCallback(async () => {
    const style = BACKGROUND_STYLES.find((s) => s.id === selectedId);
    const payload = [
      `Background style: ${selectedId}`,
      style ? `Name: ${style.name}` : '',
      `Theme: ${theme}`,
      '',
      'Reply in chat with this id when ready for the PR.',
    ].filter(Boolean).join('\n');

    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [selectedId, theme]);

  return (
    <div className="bg-style-lab">
      <Navbar />
      <div className="bg-style-lab__inner">
        <header className="bg-style-lab__header">
          <div>
            <p className="bg-style-lab__kicker">Style picker</p>
            <h1 className="bg-style-lab__title">Choose a background</h1>
            <p className="bg-style-lab__lead">
              Click a style to preview it live. Hit <strong>Select</strong> on your favorite — your choice is saved in
              this browser. Tell us the style id when you&apos;re ready and we&apos;ll wire it app-wide in a PR to{' '}
              <code>main</code>.
            </p>
            <p className="bg-style-lab__url-hint">
              Bookmark: <Link to="/style-lab/backgrounds">/style-lab/backgrounds</Link>
            </p>
          </div>
          <div className="bg-style-lab__header-actions">
            <button type="button" className="bg-style-lab__theme-btn" onClick={toggleTheme}>
              {theme === 'dark' ? <FiSun aria-hidden /> : <FiMonitor aria-hidden />}
              {theme === 'dark' ? 'Light' : 'Dark'} mode
            </button>
            <button type="button" className="bg-style-lab__copy-btn" onClick={handleCopy}>
              <FiCopy aria-hidden />
              {copied ? 'Copied' : 'Copy choice'}
            </button>
          </div>
        </header>

        <div className="bg-style-lab__selected-pill">
          Selected: <strong>{selectedId}</strong>
          {' · '}
          {BACKGROUND_STYLES.find((s) => s.id === selectedId)?.name}
        </div>

        <div className="bg-style-lab__layout">
          <div className="bg-style-lab__grid" role="list">
            {BACKGROUND_STYLES.map((style) => {
              const isPreview = style.id === previewId;
              const isSelected = style.id === selectedId;

              return (
                <article
                  key={style.id}
                  role="listitem"
                  className={[
                    'bg-style-lab__card',
                    isPreview ? 'bg-style-lab__card--preview' : '',
                    isSelected ? 'bg-style-lab__card--selected' : '',
                  ].filter(Boolean).join(' ')}
                >
                  <button
                    type="button"
                    className="bg-style-lab__card-preview-btn"
                    onClick={() => setPreviewId(style.id)}
                    aria-pressed={isPreview}
                  >
                    <span className={`bg-style-lab__thumb ${style.thumbClass}`} aria-hidden="true" />
                    <span className="bg-style-lab__card-meta">
                      <span className="bg-style-lab__card-category">{style.category}</span>
                      <span className="bg-style-lab__card-name">{style.name}</span>
                      <span className="bg-style-lab__card-id">{style.id}</span>
                      <span className="bg-style-lab__card-tagline">{style.tagline}</span>
                    </span>
                  </button>
                  <div className="bg-style-lab__card-actions">
                    <button
                      type="button"
                      className="bg-style-lab__select-btn"
                      onClick={() => handleSelect(style.id)}
                    >
                      {isSelected ? (
                        <>
                          <FiCheck aria-hidden /> Selected
                        </>
                      ) : (
                        'Select'
                      )}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="bg-style-lab__stage-wrap">
            <div className="bg-style-lab__stage-toolbar">
              <span className="bg-style-lab__stage-label">
                Live preview — <strong>{previewStyle.name}</strong>
              </span>
              <div className="bg-style-lab__context-toggle" role="group" aria-label="Preview context">
                <button
                  type="button"
                  className={previewContext === 'login' ? 'is-active' : ''}
                  onClick={() => setPreviewContext('login')}
                >
                  Login card
                </button>
                <button
                  type="button"
                  className={previewContext === 'app' ? 'is-active' : ''}
                  onClick={() => setPreviewContext('app')}
                >
                  App page
                </button>
              </div>
            </div>
            <div className="bg-style-lab__stage">
              <StyleBackdrop
                key={`${previewId}-${theme}`}
                styleId={previewId}
                deferWaves={false}
                interactive={previewStyle.shell === 'auth-studio'}
                className="bg-style-lab__stage-backdrop"
              />
              <div className="bg-style-lab__stage-content">
                {previewContext === 'login' ? <MockAuthCard /> : <MockAppCard />}
              </div>
            </div>
            <p className="bg-style-lab__stage-foot">
              Best for: {previewStyle.recommendedFor}
              {previewStyle.vantaPreset ? ` · Vanta: ${previewStyle.vantaPreset}` : ' · CSS only (no WebGL)'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
