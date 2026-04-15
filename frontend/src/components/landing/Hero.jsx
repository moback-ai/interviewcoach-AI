import React, { useState, useEffect } from 'react';
import Button from '@/components/ui/Button';
import { useTheme } from '@/hooks/useTheme';
import { motion } from 'framer-motion';

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
    <section className="relative pt-20 sm:pt-24 md:pt-32 lg:pt-36 pb-16 sm:pb-20 md:pb-28 lg:pb-32 bg-[var(--color-bg)] text-[var(--color-text-primary)] overflow-hidden">
      
      {/* Soft Gradient Background */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-[var(--color-primary)]/10 via-[var(--color-accent)]/10 to-transparent dark:from-[var(--color-primary)]/20 dark:via-[var(--color-accent)]/20 blur-3xl opacity-40 pointer-events-none" />

      <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 grid grid-cols-1 lg:grid-cols-2 gap-8 sm:gap-12 md:gap-16 items-center">
        
        {/* LEFT TEXT SIDE WITH ANIMATION */}
        <motion.div
          className="text-center md:text-center lg:text-left order-2 lg:order-1"
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        >
          <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl xl:text-6xl font-extrabold leading-tight tracking-tight mb-4 sm:mb-6">
            Your <span className="text-[var(--color-primary)]">AI-Powered</span><br className="hidden sm:inline" /> Interview Coach
          </h1>

          <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] mb-6 sm:mb-8 md:mb-10 max-w-xl mx-auto lg:mx-0 leading-relaxed">
            Upload your resume and job description. Get tailored questions and practice real interviews with AI — all in one place.
          </p>

          <div className="flex flex-col sm:flex-row justify-center lg:justify-start gap-3 sm:gap-4">
            <Button to="/upload" variant="primary">Try It Now</Button>
            <Button to="/faq" variant="secondary">Learn More</Button>
          </div>
        </motion.div>

        {/* RIGHT IMAGE WITH SMOOTH TRANSITION AND GLOW */}
        <div className="flex justify-center relative z-10 order-1 lg:order-2">
          {/* Animated Glow Effect */}
          <motion.div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-[var(--color-primary)] rounded-full blur-3xl opacity-20 z-[-1]"
            animate={{ scale: [1, 1.05, 1], opacity: [0.2, 0.3, 0.2] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          />

          {/* Image Container with Crossfade Effect */}
          <div className="relative w-full max-w-[280px] sm:max-w-[400px] md:max-w-[500px] lg:max-w-[640px] xl:max-w-[720px]">
            {/* Current Image */}
            {currentImage && (
              <motion.img
                key={currentImage}
                src={currentImage}
                alt="Interview Coach Preview"
                className="w-full drop-shadow-xl rounded-2xl sm:rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-1"
                initial={{ opacity: 0 }}
                animate={{ opacity: imageLoaded ? 1 : 0 }}
                transition={{ 
                  duration: 0.4, 
                  ease: [0.4, 0, 0.2, 1] // Custom easing for smoother transition
                }}
              />
            )}
            
            {/* Loading State - Only show on mobile for better UX */}
            {!imageLoaded && (
              <motion.div
                className="absolute inset-0 bg-[var(--color-card)] rounded-2xl sm:rounded-3xl border border-[var(--color-border)] flex items-center justify-center"
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
