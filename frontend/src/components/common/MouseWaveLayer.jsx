import { useEffect, useRef } from 'react';
import { useTheme } from '../../hooks/useTheme';

const PALETTE = {
  light: {
    ripple: [51, 102, 255],
    rippleAlt: [20, 184, 166],
    glow: [59, 130, 246],
    glowAlt: [45, 212, 191],
  },
  dark: {
    ripple: [102, 153, 255],
    rippleAlt: [52, 211, 153],
    glow: [96, 165, 250],
    glowAlt: [45, 212, 191],
  },
};

const SPAWN_INTERVAL_MS = 42;
const MAX_RIPPLES = 16;
const GLOW_RADIUS = 260;
const GLOW_FOLLOW = 0.2;

const shouldSkip = () => {
  if (typeof window === 'undefined') {
    return true;
  }
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return true;
  }
  if (window.matchMedia('(pointer: coarse)').matches) {
    return true;
  }
  return false;
};

class Ripple {
  constructor(x, y, rgb, alt = false) {
    this.x = x;
    this.y = y;
    this.rgb = rgb;
    this.alt = alt;
    this.radius = 6;
    this.opacity = alt ? 0.48 : 0.72;
    this.lineWidth = alt ? 2.4 : 3.2;
    this.speed = alt ? 3.4 : 4.2;
    this.maxRadius = alt ? 170 : 210;
  }

  update() {
    this.radius += this.speed;
    this.opacity -= this.alt ? 0.014 : 0.018;
    this.lineWidth *= 0.982;
    return this.opacity > 0.02 && this.radius < this.maxRadius;
  }

  draw(ctx) {
    const [r, g, b] = this.rgb;

    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${this.opacity})`;
    ctx.lineWidth = this.lineWidth;
    ctx.stroke();

    if (!this.alt && this.opacity > 0.2) {
      ctx.beginPath();
      ctx.arc(this.x, this.y, Math.max(0, this.radius - 14), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${this.opacity * 0.35})`;
      ctx.lineWidth = Math.max(1, this.lineWidth * 0.55);
      ctx.stroke();
    }
  }
}

export default function MouseWaveLayer({ className = '' }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (shouldSkip()) {
      return undefined;
    }

    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) {
      return undefined;
    }

    const ctx = canvas.getContext('2d');
    const ripples = [];
    let frameId = null;
    let lastSpawn = 0;
    let pointerX = -9999;
    let pointerY = -9999;
    let glowX = -9999;
    let glowY = -9999;
    let width = 0;
    let height = 0;
    let dpr = 1;

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = container.clientWidth;
      height = container.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    let rippleToggle = false;

    const spawnRipple = (x, y) => {
      if (ripples.length >= MAX_RIPPLES) {
        ripples.shift();
      }
      const colors = PALETTE[theme] || PALETTE.light;
      const useAlt = rippleToggle;
      rippleToggle = !rippleToggle;
      ripples.push(new Ripple(
        x,
        y,
        useAlt ? colors.rippleAlt : colors.ripple,
        useAlt,
      ));
    };

    const handlePointerMove = (event) => {
      const rect = container.getBoundingClientRect();
      const inside = event.clientX >= rect.left
        && event.clientX <= rect.right
        && event.clientY >= rect.top
        && event.clientY <= rect.bottom;

      if (!inside) {
        pointerX = -9999;
        pointerY = -9999;
        return;
      }

      pointerX = event.clientX - rect.left;
      pointerY = event.clientY - rect.top;

      const now = performance.now();
      if (now - lastSpawn > SPAWN_INTERVAL_MS) {
        lastSpawn = now;
        spawnRipple(pointerX, pointerY);
      }
    };

    const draw = () => {
      const colors = PALETTE[theme] || PALETTE.light;
      glowX += (pointerX - glowX) * GLOW_FOLLOW;
      glowY += (pointerY - glowY) * GLOW_FOLLOW;

      ctx.clearRect(0, 0, width, height);

      if (glowX > -100 && glowY > -100) {
        const gradient = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, GLOW_RADIUS);
        gradient.addColorStop(0, `rgba(${colors.glow[0]}, ${colors.glow[1]}, ${colors.glow[2]}, 0.26)`);
        gradient.addColorStop(0.35, `rgba(${colors.glowAlt[0]}, ${colors.glowAlt[1]}, ${colors.glowAlt[2]}, 0.12)`);
        gradient.addColorStop(0.7, `rgba(${colors.glow[0]}, ${colors.glow[1]}, ${colors.glow[2]}, 0.04)`);
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
      }

      for (let index = ripples.length - 1; index >= 0; index -= 1) {
        const ripple = ripples[index];
        ripple.draw(ctx);
        if (!ripple.update()) {
          ripples.splice(index, 1);
        }
      }

      frameId = window.requestAnimationFrame(draw);
    };

    resize();
    frameId = window.requestAnimationFrame(draw);

    const resizeObserver = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(resize)
      : null;
    resizeObserver?.observe(container);
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', handlePointerMove, { passive: true });

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', handlePointerMove);
    };
  }, [theme]);

  if (shouldSkip()) {
    return null;
  }

  const layerClass = ['mouse-wave-layer', className].filter(Boolean).join(' ');

  return (
    <div ref={containerRef} className={layerClass} aria-hidden="true">
      <canvas ref={canvasRef} className="mouse-wave-layer__canvas" />
    </div>
  );
}
