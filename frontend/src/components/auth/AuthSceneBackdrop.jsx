import { useAuthSceneParallax } from '../../hooks/useAuthSceneParallax';

export default function AuthSceneBackdrop({ variant = 'night', className = '' }) {
  const { shellRef, onPointerMove, onPointerLeave } = useAuthSceneParallax();

  const rootClass = [
    'auth-scene-backdrop',
    `auth-scene-${variant}`,
    className,
  ].filter(Boolean).join(' ');

  return (
    <div
      ref={shellRef}
      className={rootClass}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
      aria-hidden="true"
    >
      <div className="auth-scene-grid" />
      <div className="auth-scene-flare" />
      <div className="auth-scene-orb auth-scene-orb-a" />
      <div className="auth-scene-orb auth-scene-orb-b" />
      <div className="auth-scene-ray auth-scene-ray-a" />
      <div className="auth-scene-ray auth-scene-ray-b" />
      <div className="auth-scene-ring auth-scene-ring-a" />
      <div className="auth-scene-ring auth-scene-ring-b" />
      <div className="auth-scene-noise" />
    </div>
  );
}
