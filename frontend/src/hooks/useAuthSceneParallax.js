import { useEffect, useRef } from 'react';

export function useAuthSceneParallax() {
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

  const onPointerMove = (event) => {
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

  const onPointerLeave = () => {
    queueBackgroundMotion(0, 0);
  };

  return { shellRef, onPointerMove, onPointerLeave };
}
