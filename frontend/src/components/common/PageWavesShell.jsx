import AnimatedWavesLayer from './AnimatedWavesLayer';

export default function PageWavesShell({
  children,
  className = '',
  contentClassName = '',
  preset = 'subtle',
  deferWaves = true,
}) {
  const shellClassName = ['page-waves-shell', className].filter(Boolean).join(' ');
  const bodyClassName = ['page-waves-shell__content', contentClassName].filter(Boolean).join(' ');

  return (
    <div className={shellClassName}>
      <div className="page-waves-shell__backdrop">
        <div className="page-waves-shell__backdrop-fill" />
        <div className="page-waves-shell__backdrop-aurora page-waves-shell__backdrop-aurora-a" aria-hidden="true" />
        <div className="page-waves-shell__backdrop-aurora page-waves-shell__backdrop-aurora-b" aria-hidden="true" />
        <AnimatedWavesLayer
          className="page-waves-shell__backdrop-vanta"
          preset={preset}
          defer={deferWaves}
        />
        <div className="page-waves-shell__backdrop-grid" />
        <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-a" aria-hidden="true" />
        <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-b" aria-hidden="true" />
      </div>
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}
