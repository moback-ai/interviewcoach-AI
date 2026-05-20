import StyleBackdrop from './StyleBackdrop';
import { APP_BACKGROUND_STYLE_ID } from '../../lib/backgroundStyles';

const PRESET_TO_STYLE_ID = {
  subtle: 'soft-cloud',
  upload: 'calm-upload',
  landing: 'landing-breeze',
};

export default function PageWavesShell({
  children,
  className = '',
  contentClassName = '',
  styleId,
  preset,
  deferWaves = true,
}) {
  const resolvedStyleId = styleId
    || (preset && PRESET_TO_STYLE_ID[preset])
    || APP_BACKGROUND_STYLE_ID;

  const shellClassName = ['page-waves-shell', className].filter(Boolean).join(' ');
  const bodyClassName = ['page-waves-shell__content', contentClassName].filter(Boolean).join(' ');

  return (
    <div className={shellClassName}>
      <StyleBackdrop
        styleId={resolvedStyleId}
        deferWaves={deferWaves}
        className="page-waves-shell__backdrop style-backdrop--page"
      />
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}
