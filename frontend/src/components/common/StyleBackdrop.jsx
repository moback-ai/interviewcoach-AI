import AnimatedWavesLayer from './AnimatedWavesLayer';
import { getBackgroundStyleById } from '../../lib/backgroundStyles';

export default function StyleBackdrop({
  styleId,
  className = '',
  interactive = false,
  deferWaves = true,
}) {
  const style = getBackgroundStyleById(styleId);
  const rootClass = ['style-backdrop', className].filter(Boolean).join(' ');

  if (style.shell === 'css') {
    return (
      <div className={`${rootClass} style-backdrop--css`} aria-hidden="true">
        <div className={`style-backdrop__css-canvas ${style.cssClass}`} />
      </div>
    );
  }

  if (style.shell === 'auth-studio') {
    return (
      <div className={`${rootClass} auth-studio-page-backdrop style-backdrop--auth`} aria-hidden="true">
        <AnimatedWavesLayer
          className="auth-studio-page-vanta"
          preset={style.vantaPreset}
          defer={deferWaves}
          interactive={interactive}
        />
        <div className="auth-studio-page-aurora auth-studio-page-aurora-a" />
        <div className="auth-studio-page-aurora auth-studio-page-aurora-b" />
        <div className="auth-studio-page-grid" />
        <div className="auth-studio-page-shade" />
      </div>
    );
  }

  return (
    <div className={`${rootClass} style-backdrop--page`} aria-hidden="true">
      <div className="page-waves-shell__backdrop-fill" />
      <div className="page-waves-shell__backdrop-aurora page-waves-shell__backdrop-aurora-a" />
      <div className="page-waves-shell__backdrop-aurora page-waves-shell__backdrop-aurora-b" />
      <AnimatedWavesLayer
        className="page-waves-shell__backdrop-vanta"
        preset={style.vantaPreset}
        defer={deferWaves}
        interactive={interactive}
      />
      <div className="page-waves-shell__backdrop-grid" />
      <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-a" />
      <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-b" />
    </div>
  );
}
