import { lazy, Suspense, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Hero from '../components/landing/Hero';
import { trackEvents } from '../services/mixpanel';

const FeatureHighlights = lazy(() => import('../components/landing/FeatureHighlights'));
const HowItWorks = lazy(() => import('../components/landing/HowItWorks'));
const UseCases = lazy(() => import('../components/landing/UseCases'));
const FAQ = lazy(() => import('../components/landing/FAQ'));
const CallToAction = lazy(() => import('../components/landing/CallToAction'));

function Landing() {
  const location = useLocation();
  const hasTrackedLandingVisit = useRef(false);

  useEffect(() => {
    if (!hasTrackedLandingVisit.current) {
      hasTrackedLandingVisit.current = true;
      trackEvents.landingPageVisit();
    }
  }, []);

  useEffect(() => {
    if (!location.hash) {
      return undefined;
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
    <div className="landing-shell">
      <div className="landing-shell__bg bg-style-aurora-dream" aria-hidden="true" />
      <Navbar />
      <main className="landing-shell__main relative overflow-hidden">
        <Hero />
        <Suspense fallback={null}>
          <section id="features" className="landing-section">
            <FeatureHighlights />
          </section>
          <section id="how-it-works" className="landing-section">
            <HowItWorks />
          </section>
          <section id="use-cases" className="landing-section">
            <UseCases />
          </section>
          <section id="faq" className="landing-section">
            <FAQ />
          </section>
          <section id="contact" className="landing-section">
            <CallToAction />
          </section>
        </Suspense>
      </main>
    </div>
  );
}

export default Landing;
