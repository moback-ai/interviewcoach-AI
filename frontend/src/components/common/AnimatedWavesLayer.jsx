import { useEffect, useRef } from 'react';
import { useTheme } from '../../hooks/useTheme';

const EFFECT_PRESETS = {
  subtle: {
    light: {
      backgroundColor: 0xe8f5ff,
      color: 0x5ebfff,
      shininess: 32,
      waveHeight: 8,
      waveSpeed: 0.48,
      zoom: 0.92,
    },
    dark: {
      backgroundColor: 0x071526,
      color: 0x185b8c,
      shininess: 26,
      waveHeight: 7,
      waveSpeed: 0.4,
      zoom: 0.9,
    },
  },
  auth: {
    light: {
      backgroundColor: 0x177fc9,
      color: 0x1a8fe2,
      shininess: 38,
      waveHeight: 18,
      waveSpeed: 0.85,
      zoom: 1.05,
    },
    dark: {
      backgroundColor: 0x0b406e,
      color: 0x2196f3,
      shininess: 34,
      waveHeight: 15,
      waveSpeed: 0.72,
      zoom: 0.98,
    },
  },
  landing: {
    light: {
      backgroundColor: 0xe6f7ff,
      color: 0x64c5ff,
      shininess: 34,
      waveHeight: 10,
      waveSpeed: 0.54,
      zoom: 0.94,
    },
    dark: {
      backgroundColor: 0x091c31,
      color: 0x206da5,
      shininess: 28,
      waveHeight: 9,
      waveSpeed: 0.46,
      zoom: 0.92,
    },
  },
};

const getPresetOptions = (theme, preset) => {
  const resolvedPreset = EFFECT_PRESETS[preset] || EFFECT_PRESETS.subtle;
  return resolvedPreset[theme] || resolvedPreset.light;
};

export default function AnimatedWavesLayer({
  className = '',
  preset = 'subtle',
}) {
  const elementRef = useRef(null);
  const instanceRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    let cancelled = false;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const mountEffect = async () => {
      if (!elementRef.current || prefersReducedMotion) {
        return;
      }

      const THREE = await import('three');
      window.THREE = THREE;
      const { default: WAVES } = await import('vanta/dist/vanta.waves.min');

      if (cancelled || !elementRef.current) {
        return;
      }

      const baseOptions = {
        el: elementRef.current,
        THREE,
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200,
        minWidth: 200,
        scale: 1,
        scaleMobile: 1,
        backgroundAlpha: 1,
        ...getPresetOptions(theme, preset),
      };

      if (window.innerWidth < 768) {
        baseOptions.waveHeight = Math.max(5, baseOptions.waveHeight - 3);
        baseOptions.zoom = Math.max(0.84, baseOptions.zoom - 0.08);
      }

      if (instanceRef.current) {
        instanceRef.current.setOptions(baseOptions);
        return;
      }

      instanceRef.current = WAVES(baseOptions);
    };

    mountEffect().catch((error) => {
      console.error('Unable to initialize animated waves background:', error);
    });

    return () => {
      cancelled = true;
      if (instanceRef.current) {
        instanceRef.current.destroy();
        instanceRef.current = null;
      }
    };
  }, [preset, theme]);

  return <div ref={elementRef} className={className} aria-hidden="true" />;
}
