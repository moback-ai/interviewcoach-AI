import { useState } from 'react';
import Button from '@/components/ui/Button';
import { useTheme } from '@/hooks/useTheme';

const metrics = [
  { value: '3 mins', label: 'to generate a mock interview' },
  { value: 'Voice AI', label: 'real-time interviewer responses' },
  { value: 'Tailored', label: 'role and resume aware questions' },
];

function Hero() {
  const { isDark } = useTheme();
  const [imageLoaded, setImageLoaded] = useState(false);

  const heroImage = isDark
    ? '/assets/landing/hero/hero-dark.jpg'
    : '/assets/landing/hero/hero-light.jpg';

  return (
    <section className="landing-hero relative pt-20 sm:pt-24 md:pt-32 lg:pt-36 pb-16 sm:pb-20 md:pb-28 lg:pb-32 text-[var(--color-text-primary)] overflow-hidden">
      <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 grid grid-cols-1 lg:grid-cols-2 gap-8 sm:gap-12 md:gap-16 items-center">
        <div className="text-center lg:text-left order-2 lg:order-1 landing-hero__copy">
          <div
            className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)]/70 px-3 py-1.5 text-xs sm:text-sm font-medium text-[var(--color-text-secondary)] shadow-lg backdrop-blur-xl"
            style={{ backgroundColor: 'color-mix(in srgb, var(--color-card) 75%, transparent)' }}
          >
            <span className="h-2 w-2 rounded-full bg-[var(--color-primary)]" />
            Premium AI mock interviews with live voice coaching
          </div>

          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-6xl font-extrabold leading-tight tracking-tight mb-4 sm:mb-6 mt-4">
            Prepare like an
            <span className="block bg-gradient-to-r from-[var(--color-primary)] via-[var(--color-accent)] to-sky-400 bg-clip-text text-transparent">
              world-class candidate
            </span>
          </h1>

          <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] mb-6 sm:mb-8 md:mb-10 max-w-xl mx-auto lg:mx-0 leading-relaxed">
            Upload your resume, match it to the role, and run a polished voice-led mock interview with feedback that feels fast, focused, and human.
          </p>

          <div className="flex flex-col sm:flex-row justify-center lg:justify-start gap-3 sm:gap-4">
            <Button to="/upload" variant="primary">Try It Now</Button>
            <Button to="/faq" variant="secondary">Learn More</Button>
          </div>

          <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
            {metrics.map((metric) => (
              <div key={metric.label} className="glass-panel rounded-2xl px-4 py-4">
                <div className="text-lg font-semibold text-[var(--color-text-primary)]">{metric.value}</div>
                <div className="mt-1 text-xs sm:text-sm text-[var(--color-text-secondary)]">{metric.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-center relative z-10 order-1 lg:order-2">
          <div className="relative w-full max-w-[280px] sm:max-w-[400px] md:max-w-[500px] lg:max-w-[640px]">
            <img
              src={heroImage}
              alt="Interview Coach preview"
              width="1536"
              height="1024"
              loading="lazy"
              decoding="async"
              onLoad={() => setImageLoaded(true)}
              className={`w-full drop-shadow-xl rounded-[2rem] border border-[var(--color-border)]/70 bg-[var(--color-card)]/80 p-2 shadow-[0_40px_120px_rgba(15,23,42,0.18)] transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            />

            {!imageLoaded ? (
              <div
                className="absolute inset-0 bg-[var(--color-card)] rounded-[2rem] border border-[var(--color-border)] flex items-center justify-center"
                aria-hidden="true"
              >
                <div className="w-8 h-8 sm:w-10 sm:h-10 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

export default Hero;
