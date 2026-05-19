import React, { useEffect, useRef } from 'react';

export default function AuthSceneShell({
  variant = 'night',
  badge,
  icon,
  title,
  description,
  children,
  footer,
}) {
  const shellRef = useRef(null);
  const motionFrameRef = useRef(null);
  const prefersReducedMotionRef = useRef(false);

  useEffect(() => {
    prefersReducedMotionRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return () => {
      if (motionFrameRef.current) {
        window.cancelAnimationFrame(motionFrameRef.current);
      }
    };
  }, []);

  const applyBackgroundMotion = (offsetX, offsetY) => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    shell.style.setProperty('--auth-scene-shift-x', `${offsetX * 24}px`);
    shell.style.setProperty('--auth-scene-shift-y', `${offsetY * 20}px`);
    shell.style.setProperty('--auth-scene-tilt', `${offsetX * 3.5}deg`);
  };

  const queueBackgroundMotion = (offsetX, offsetY) => {
    if (prefersReducedMotionRef.current) {
      return;
    }

    if (motionFrameRef.current) {
      window.cancelAnimationFrame(motionFrameRef.current);
    }

    motionFrameRef.current = window.requestAnimationFrame(() => {
      applyBackgroundMotion(offsetX, offsetY);
      motionFrameRef.current = null;
    });
  };

  const handlePointerMove = (event) => {
    if (event.pointerType === 'touch' || prefersReducedMotionRef.current) {
      return;
    }

    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    const bounds = shell.getBoundingClientRect();
    const relativeX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
    const relativeY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
    queueBackgroundMotion(relativeX, relativeY);
  };

  const handlePointerLeave = () => {
    queueBackgroundMotion(0, 0);
  };

  return (
    <div
      ref={shellRef}
      className={`auth-scene-shell auth-scene-${variant}`}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <div className="auth-scene-grid" aria-hidden="true" />
      <div className="auth-scene-flare" aria-hidden="true" />
      <div className="auth-scene-orb auth-scene-orb-a" aria-hidden="true" />
      <div className="auth-scene-orb auth-scene-orb-b" aria-hidden="true" />
      <div className="auth-scene-ray auth-scene-ray-a" aria-hidden="true" />
      <div className="auth-scene-ray auth-scene-ray-b" aria-hidden="true" />
      <div className="auth-scene-ring auth-scene-ring-a" aria-hidden="true" />
      <div className="auth-scene-ring auth-scene-ring-b" aria-hidden="true" />
      <div className="auth-scene-noise" aria-hidden="true" />

      <div className="auth-scene-panel-wrap">
        <section className="auth-scene-card">
          {(badge || icon || title || description) && (
            <header className="auth-scene-header">
              {(badge || icon) && (
                <div className="auth-scene-badge-wrap">
                  {icon ? <span className="auth-scene-icon">{icon}</span> : null}
                  {badge ? <span className="auth-scene-badge">{badge}</span> : null}
                </div>
              )}
              {title ? <h1 className="auth-scene-title">{title}</h1> : null}
              {description ? <p className="auth-scene-copy">{description}</p> : null}
            </header>
          )}

          <div className="auth-scene-content">{children}</div>
          {footer ? <div className="auth-scene-footer">{footer}</div> : null}
        </section>
      </div>
    </div>
  );
}
