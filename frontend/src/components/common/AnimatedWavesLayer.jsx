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
  upload: {
    light: {
      backgroundColor: 0xeaf6ff,
      color: 0x6eb8ff,
      shininess: 24,
      waveHeight: 6,
      waveSpeed: 0.35,
      zoom: 0.88,
    },
    dark: {
      backgroundColor: 0x081a2e,
      color: 0x1a6ba8,
      shininess: 22,
      waveHeight: 5,
      waveSpeed: 0.3,
      zoom: 0.86,
    },
  },
  auth: {
    light: {
      backgroundColor: 0x1565c0,
      color: 0x2196f3,
      shininess: 45,
      waveHeight: 20,
      waveSpeed: 1.15,
      zoom: 1,
    },
    dark: {
      backgroundColor: 0x0a2f52,
      color: 0x1e88e5,
      shininess: 40,
      waveHeight: 18,
      waveSpeed: 1,
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

const scheduleIdle = (callback) => {
  if (typeof window.requestIdleCallback === 'function') {
    return window.requestIdleCallback(callback, { timeout: 2200 });
  }
  return window.setTimeout(callback, 120);
};

const cancelIdle = (handle) => {
  if (typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(handle);
    return;
  }
  window.clearTimeout(handle);
};

export default function AnimatedWavesLayer({
  className = '',
  preset = 'subtle',
  defer = true,
  interactive = false,
}) {
  const elementRef = useRef(null);
  const instanceRef = useRef(null);
  const idleHandleRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    let cancelled = false;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const mountEffect = async () => {
      if (!elementRef.current || prefersReducedMotion || cancelled) {
        return;
      }

      const THREE = await import('three');
      const { default: WAVES } = await import('vanta/dist/vanta.waves.min');

      if (cancelled || !elementRef.current) {
        return;
      }

      const baseOptions = {
        el: elementRef.current,
        THREE,
        mouseControls: interactive,
        touchControls: interactive,
        gyroControls: false,
        minHeight: 200,
        minWidth: 200,
        scale: 1,
        scaleMobile: 1,
        backgroundAlpha: 1,
        ...getPresetOptions(theme, preset),
      };

      if (window.innerWidth < 768) {
        baseOptions.waveHeight = Math.max(4, baseOptions.waveHeight - 2);
        baseOptions.zoom = Math.max(0.82, baseOptions.zoom - 0.06);
      }

      if (instanceRef.current) {
        instanceRef.current.setOptions(baseOptions);
        return;
      }

      instanceRef.current = WAVES(baseOptions);
    };

    const startMount = () => {
      mountEffect().catch((error) => {
        console.error('Unable to initialize animated waves background:', error);
      });
    };

    if (defer) {
      idleHandleRef.current = scheduleIdle(startMount);
    } else {
      startMount();
    }

    const handleVisibility = () => {
      if (!instanceRef.current) {
        return;
      }
      if (document.hidden) {
        instanceRef.current.setOptions({ waveSpeed: 0.05 });
      } else {
        instanceRef.current.setOptions(getPresetOptions(theme, preset));
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', handleVisibility);
      if (idleHandleRef.current) {
        cancelIdle(idleHandleRef.current);
        idleHandleRef.current = null;
      }
      if (instanceRef.current) {
        instanceRef.current.destroy();
        instanceRef.current = null;
      }
    };
  }, [defer, interactive, preset, theme]);

  const layerClass = ['animated-waves-layer', className].filter(Boolean).join(' ');

  return <div ref={elementRef} className={layerClass} aria-hidden="true" />;
}
