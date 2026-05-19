import React, { useEffect, useRef } from 'react';
import AnimatedWavesLayer from '../common/AnimatedWavesLayer';

export default function AuthSimpleShell({
  eyebrow,
  title,
  description,
  wide = false,
  children,
  footer,
}) {
  const shellRef = useRef(null);
  const frameRef = useRef(null);
  const reducedMotionRef = useRef(false);
  const motionFrameRef = useRef(null);

  useEffect(() => {
    reducedMotionRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return () => {
      if (motionFrameRef.current) {
        window.cancelAnimationFrame(motionFrameRef.current);
      }
    };
  }, []);

  const applyMotion = (offsetX, offsetY) => {
    const shell = shellRef.current;
    const frame = frameRef.current;
    if (!shell || !frame) {
      return;
    }

    shell.style.setProperty('--auth-simple-bg-x', `${offsetX * -22}px`);
    shell.style.setProperty('--auth-simple-bg-y', `${offsetY * -16}px`);
    shell.style.setProperty('--auth-simple-glow-x', `${offsetX * 18}px`);
    shell.style.setProperty('--auth-simple-glow-y', `${offsetY * 14}px`);
    frame.style.transform = `perspective(1200px) rotateX(${offsetY * -2.2}deg) rotateY(${offsetX * 3.4}deg) translate3d(${offsetX * 6}px, ${offsetY * 5}px, 0)`;
  };

  const queueMotion = (offsetX, offsetY) => {
    if (reducedMotionRef.current) {
      return;
    }

    if (motionFrameRef.current) {
      window.cancelAnimationFrame(motionFrameRef.current);
    }

    motionFrameRef.current = window.requestAnimationFrame(() => {
      applyMotion(offsetX, offsetY);
      motionFrameRef.current = null;
    });
  };

  const handlePointerMove = (event) => {
    if (event.pointerType === 'touch' || reducedMotionRef.current) {
      return;
    }

    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    const bounds = shell.getBoundingClientRect();
    const offsetX = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
    const offsetY = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
    queueMotion(offsetX, offsetY);
  };

  const handlePointerLeave = () => {
    queueMotion(0, 0);
  };

  return (
    <div
      ref={shellRef}
      className="auth-simple-page"
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <div className="auth-simple-backdrop" aria-hidden="true">
        <div className="auth-simple-backdrop-image" />
        <AnimatedWavesLayer className="auth-simple-backdrop-vanta" preset="auth" />
        <div className="auth-simple-backdrop-grid" />
        <div className="auth-simple-backdrop-glow auth-simple-backdrop-glow-a" />
        <div className="auth-simple-backdrop-glow auth-simple-backdrop-glow-b" />
      </div>

      <section
        ref={frameRef}
        className={`auth-simple-card ${wide ? 'auth-simple-card-wide' : ''}`}
      >
        <header className="auth-simple-header">
          {eyebrow ? <p className="auth-simple-eyebrow">{eyebrow}</p> : null}
          {title ? <h1 className="auth-simple-title">{title}</h1> : null}
          {description ? <p className="auth-simple-copy">{description}</p> : null}
        </header>

        <div className="auth-simple-content">{children}</div>
        {footer ? <div className="auth-simple-footer">{footer}</div> : null}
      </section>
    </div>
  );
}
