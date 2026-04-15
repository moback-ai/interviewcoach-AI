import React, { useEffect, useRef } from 'react';
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
    <>
      <Navbar />
      <Hero />
      <FeatureHighlights />
      <HowItWorks />
      <UseCases/>
      <FAQ/>
      <CallToAction/>
    </>
  );
}

export default Landing;
