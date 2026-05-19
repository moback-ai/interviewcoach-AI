import React, { useEffect, useRef } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { useLocation } from 'react-router-dom';
import Navbar from '../components/Navbar';
import PageWavesShell from '../components/common/PageWavesShell';
import Hero from '../components/landing/Hero';
import FeatureHighlights from '../components/landing/FeatureHighlights';
import HowItWorks  from '../components/landing/HowItWorks';
import UseCases from '../components/landing/UseCases';
import FAQ from '../components/landing/FAQ';
import CallToAction from '../components/landing/CallToAction';
import { trackEvents } from '../services/mixpanel';

function Landing() {
  const location = useLocation();
  const prefersReducedMotion = useReducedMotion();

  // Prevent duplicate event tracking
  const hasTrackedLandingVisit = useRef(false);
  
  // Track landing page visit (once per page load)
  useEffect(() => {
    if (!hasTrackedLandingVisit.current) {
      hasTrackedLandingVisit.current = true;
      trackEvents.landingPageVisit();
    }
  }, []);

  useEffect(() => {
    if (!location.hash) {
      return;
    }

    let frameId = null;
    const targetId = location.hash.slice(1);

    const scrollToHashTarget = () => {
      const target = document.getElementById(targetId);

      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }

      frameId = window.requestAnimationFrame(scrollToHashTarget);
    };

    frameId = window.requestAnimationFrame(scrollToHashTarget);

    return () => {
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [location.hash]);

  return (
    <PageWavesShell preset="landing" contentClassName="relative overflow-hidden">
      <div className="ambient-orb h-72 w-72 left-[-4rem] top-20 opacity-80" />
      <div className="ambient-orb h-80 w-80 right-[-6rem] top-[28rem] opacity-70" />
      <Navbar />
      <motion.main
        initial={prefersReducedMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      >
        <Hero />
        <motion.div
          id="features"
          className="landing-section"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.12 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <FeatureHighlights />
        </motion.div>
        <motion.div
          id="how-it-works"
          className="landing-section"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.12 }}
          transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1], delay: 0.04 }}
        >
          <HowItWorks />
        </motion.div>
        <motion.div
          id="use-cases"
          className="landing-section"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.12 }}
          transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1], delay: 0.06 }}
        >
          <UseCases />
        </motion.div>
        <motion.div
          id="faq"
          className="landing-section"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.12 }}
          transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
        >
          <FAQ />
        </motion.div>
        <motion.div
          id="contact"
          className="landing-section"
          initial={prefersReducedMotion ? false : { opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.12 }}
          transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
        >
          <CallToAction />
        </motion.div>
      </motion.main>
    </PageWavesShell>
  );
}

export default Landing;
