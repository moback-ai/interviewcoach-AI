import React, { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import Navbar from '../components/Navbar';
import Hero from '../components/landing/Hero';
import FeatureHighlights from '../components/landing/FeatureHighlights';
import HowItWorks  from '../components/landing/HowItWorks';
import UseCases from '../components/landing/UseCases';
import FAQ from '../components/landing/FAQ';
import CallToAction from '../components/landing/CallToAction';
import { trackEvents } from '../services/mixpanel';

function Landing() {
  // Prevent duplicate event tracking
  const hasTrackedLandingVisit = useRef(false);
  
  // Track landing page visit (once per page load)
  useEffect(() => {
    if (!hasTrackedLandingVisit.current) {
      hasTrackedLandingVisit.current = true;
      trackEvents.landingPageVisit();
    }
  }, []);

  return (
    <div className="relative overflow-hidden">
      <div className="ambient-orb h-72 w-72 left-[-4rem] top-20 opacity-80" />
      <div className="ambient-orb h-80 w-80 right-[-6rem] top-[28rem] opacity-70" />
      <Navbar />
      <motion.main
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      >
        <Hero />
        <FeatureHighlights />
        <HowItWorks />
        <UseCases />
        <FAQ />
        <CallToAction />
      </motion.main>
    </div>
  );
}

export default Landing;
