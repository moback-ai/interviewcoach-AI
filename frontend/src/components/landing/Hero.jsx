import React, { useState, useEffect } from 'react';
import Button from '@/components/ui/Button';
import { useTheme } from '@/hooks/useTheme';
import { motion } from 'framer-motion';

const metrics = [
  { value: '3 mins', label: 'to generate a mock interview' },
  { value: 'Voice AI', label: 'real-time interviewer responses' },
  { value: 'Tailored', label: 'role and resume aware questions' },
];

function Hero() {
  const { isDark } = useTheme();
  const [imageLoaded, setImageLoaded] = useState(false);
  const [currentImage, setCurrentImage] = useState('');

  const heroImage = isDark
    ? '/assets/landing/hero/hero-dark.png'
    : '/assets/landing/hero/hero-light.png';

  // Smooth theme transition with crossfade effect
  useEffect(() => {
    if (heroImage !== currentImage) {
      setImageLoaded(false);
      const img = new Image();
      img.onload = () => {
        setCurrentImage(heroImage);
        setImageLoaded(true);
      };
      img.src = heroImage;
    }
  }, [heroImage, currentImage]);

  return (
    <section className="relative pt-20 sm:pt-24 md:pt-32 lg:pt-36 pb-16 sm:pb-20 md:pb-28 lg:pb-32 text-[var(--color-text-primary)] overflow-hidden">
      <div className="absolute inset-0 -z-10 ai-hero-field pointer-events-none" />

      <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 grid grid-cols-1 lg:grid-cols-2 gap-8 sm:gap-12 md:gap-16 items-center">
        
        <motion.div
          className="text-center md:text-center lg:text-left order-2 lg:order-1"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05, duration: 0.55 }}
            className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)]/70 px-3 py-1.5 text-xs sm:text-sm font-medium text-[var(--color-text-secondary)] shadow-lg backdrop-blur-xl"
            style={{ backgroundColor: 'color-mix(in srgb, var(--color-card) 75%, transparent)' }}
          >
            <span className="h-2 w-2 rounded-full bg-[var(--color-primary)] shadow-[0_0_20px_var(--color-primary)]" />
            Premium AI mock interviews with live voice coaching
          </motion.div>

          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-6xl font-extrabold leading-tight tracking-tight mb-4 sm:mb-6">
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
            {metrics.map((metric, index) => (
              <motion.div
                key={metric.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 + index * 0.08, duration: 0.45 }}
                className="glass-panel rounded-2xl px-4 py-4"
              >
                <div className="text-lg font-semibold text-[var(--color-text-primary)]">{metric.value}</div>
                <div className="mt-1 text-xs sm:text-sm text-[var(--color-text-secondary)]">{metric.label}</div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        <div className="flex justify-center relative z-10 order-1 lg:order-2">
          <motion.div
            className="absolute top-1/2 left-1/2 -z-10 h-[120%] w-[120%] -translate-x-1/2 -translate-y-1/2 rounded-[2rem] border border-[var(--color-border)]/40"
            style={{
              background:
                'linear-gradient(135deg, color-mix(in srgb, var(--color-primary) 12%, transparent), transparent 44%), linear-gradient(45deg, transparent 0 48%, color-mix(in srgb, var(--color-accent) 18%, transparent) 50%, transparent 52%)'
            }}
            animate={{ y: [-8, 8, -8], opacity: [0.42, 0.7, 0.42] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          />

          <div className="relative w-full max-w-[280px] sm:max-w-[400px] md:max-w-[500px] lg:max-w-[640px] xl:max-w-[720px]">
            <motion.div
              initial={{ opacity: 0, x: 18, y: 18 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              className="floating-card absolute -right-3 top-8 hidden md:flex rounded-2xl glass-panel px-4 py-3 text-left"
            >
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--color-text-secondary)]">Interview Flow</div>
                <div className="mt-1 text-sm font-semibold">Upload, generate, rehearse, improve</div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: -18, y: -18 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ duration: 0.6, delay: 0.25 }}
              className="floating-card absolute -left-4 bottom-8 hidden md:flex rounded-2xl glass-panel px-4 py-3 text-left [animation-delay:1.4s]"
            >
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--color-text-secondary)]">Voice AI</div>
                <div className="mt-1 text-sm font-semibold">Choose a calmer or sharper interviewer</div>
              </div>
            </motion.div>

            {currentImage && (
              <motion.img
                key={currentImage}
                src={currentImage}
                alt="Interview Coach Preview"
                className="w-full drop-shadow-xl rounded-[2rem] border border-[var(--color-border)]/70 bg-[var(--color-card)]/80 p-2 shadow-[0_40px_120px_rgba(15,23,42,0.18)] backdrop-blur-xl"
                initial={{ opacity: 0, y: 18, scale: 0.98 }}
                animate={{ opacity: imageLoaded ? 1 : 0, y: imageLoaded ? 0 : 18, scale: imageLoaded ? 1 : 0.98 }}
                transition={{ 
                  duration: 0.45, 
                  ease: [0.4, 0, 0.2, 1]
                }}
              />
            )}
            
            {!imageLoaded && (
              <motion.div
                className="absolute inset-0 bg-[var(--color-card)] rounded-[2rem] border border-[var(--color-border)] flex items-center justify-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <motion.div
                  className="w-8 h-8 sm:w-10 sm:h-10 border-2 border-[var(--color-primary)] border-t-transparent rounded-full"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                />
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default Hero;
