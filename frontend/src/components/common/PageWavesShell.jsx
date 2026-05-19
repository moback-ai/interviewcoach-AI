import AnimatedWavesLayer from './AnimatedWavesLayer';

export default function PageWavesShell({
  children,
  className = '',
  contentClassName = '',
  preset = 'subtle',
}) {
  const shellClassName = ['page-waves-shell', className].filter(Boolean).join(' ');
  const bodyClassName = ['page-waves-shell__content', contentClassName].filter(Boolean).join(' ');

  return (
    <div className={shellClassName}>
      <div className="page-waves-shell__backdrop">
        <div className="page-waves-shell__backdrop-fill" />
        <AnimatedWavesLayer
          className="page-waves-shell__backdrop-vanta"
          preset={preset}
        />
        <div className="page-waves-shell__backdrop-grid" />
        <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-a" />
        <div className="page-waves-shell__backdrop-glow page-waves-shell__backdrop-glow-b" />
      </div>
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}
