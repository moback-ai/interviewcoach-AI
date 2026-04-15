import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

function WaveAnimation({ isActive, size = 160, imageSize = 128, listening = false }) {
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);

  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (!isActive) return null;

  // Calculate responsive wave sizes based on screen size
  const getResponsiveSize = () => {
    // Base size for mobile
    let baseSize = size;
    
    // Adjust based on screen size
    if (windowWidth >= 1536) { // 2xl screens
      baseSize = size * 1.2;
    } else if (windowWidth >= 1280) { // xl screens
      baseSize = size * 1.1;
    } else if (windowWidth >= 1024) { // lg screens
      baseSize = size;
    } else if (windowWidth >= 768) { // md screens
      baseSize = size * 0.9;
    } else if (windowWidth >= 640) { // sm screens
      baseSize = size * 0.8;
    } else { // xs screens
      baseSize = size * 0.7;
    }
    
    return Math.max(baseSize, 80); // Minimum size of 80px
  };

  const responsiveSize = getResponsiveSize();
  const primaryWaveSize = responsiveSize;
  const secondaryWaveSize = responsiveSize;

  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      {/* Multiple waves with irregular timing - more realistic speech pattern */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: primaryWaveSize,
          height: primaryWaveSize,
          backgroundColor: 'var(--color-text-secondary)', // Theme-aware gray
          opacity: 0.3,
        }}
        animate={listening ? {
          scale: [1.3, 1.1, 1.2, 1, 1.1, 1, 1.2], // Same radius range as speaking, but out-in pattern
          opacity: [0.1, 0.25, 0.08, 0.3, 0.12, 0.3, 0.15], // Opacity increases as it contracts
        } : {
          scale: [1, 1.2, 1, 1.3, 1, 1.1, 1], // In-out pattern for speaking
          opacity: [0.3, 0.1, 0.3, 0.05, 0.3, 0.15, 0.3], // Regular opacity pattern
        }}
        transition={{
          duration: 2.5, // Longer duration for more natural rhythm
          repeat: Infinity,
          ease: "easeInOut",
          times: [0, 0.2, 0.4, 0.6, 0.8, 0.9, 1], // Irregular timing
        }}
      />
      
      {/* Secondary wave with different timing */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: secondaryWaveSize,
          height: secondaryWaveSize,
          backgroundColor: 'var(--color-text-secondary)',
          opacity: 0.2,
        }}
        animate={listening ? {
          scale: [1.35, 1.1, 1.2, 1, 1.1, 1, 1.2], // Same radius range as speaking, but out-in pattern
          opacity: [0.05, 0.2, 0.08, 0.25, 0.1, 0.25, 0.12], // Opacity increases as it contracts
        } : {
          scale: [1, 1.4, 1, 1.1, 1, 1.35, 1], // In-out pattern for speaking
          opacity: [0.2, 0.05, 0.2, 0.1, 0.2, 0.08, 0.2], // Regular opacity pattern
        }}
        transition={{
          duration: 3.2, // Different duration for variety
          repeat: Infinity,
          ease: "easeInOut",
          times: [0, 0.15, 0.35, 0.55, 0.75, 0.9, 1], // Different timing
        }}
      />
    </div>
  );
}

export default WaveAnimation;

