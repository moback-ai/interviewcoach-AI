import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';

export default function CallToAction() {
  return (
    <section className="relative overflow-hidden bg-[var(--color-primary)] text-white py-12 sm:py-16 md:py-20 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="absolute inset-0 opacity-25 pointer-events-none bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.3),transparent_48%)]" />
      <div className="max-w-4xl mx-auto text-center">
        <motion.h2
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.45 }}
          className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold mb-4 sm:mb-6 leading-tight"
        >
          Ready to Ace Your Next Interview?
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.45, delay: 0.08 }}
          className="text-sm sm:text-base md:text-lg lg:text-xl mb-6 sm:mb-8 max-w-2xl mx-auto leading-relaxed"
        >
          Start practicing with AI-powered mock interviews tailored to your dream job.
        </motion.p>
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.45, delay: 0.12 }}
          className="flex flex-col sm:flex-row justify-center gap-3 sm:gap-4"
        >
          <Link
            to="/signup"
            className="bg-white text-[var(--color-primary)] font-semibold px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg sm:rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:bg-gray-100 shadow-md hover:shadow-lg"
          >
            Get Started Free
          </Link>
          <a
            href="#features"
            className="border border-white font-semibold px-4 sm:px-6 py-2.5 sm:py-3 rounded-lg sm:rounded-xl transition-all duration-200 hover:-translate-y-0.5 hover:bg-white hover:text-[var(--color-primary)] shadow-md hover:shadow-lg"
          >
            Explore Features
          </a>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.5, delay: 0.18 }}
          className="mt-8 sm:mt-10 rounded-3xl border border-white/25 bg-white/10 p-5 sm:p-6 text-left shadow-[0_20px_60px_rgba(15,23,42,0.18)] backdrop-blur-md"
        >
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-white/80">Need Help?</p>
              <p className="mt-2 text-sm sm:text-base text-white/90 leading-relaxed">
                Use the help center for product questions, or email billing support if you have payment issues.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link
                to="/faq#contact"
                className="inline-flex items-center justify-center rounded-xl bg-white px-4 py-3 text-sm font-semibold text-[var(--color-primary)] transition-transform duration-200 hover:-translate-y-0.5"
              >
                Open Help Center
              </Link>
              <a
                href="mailto:support@dodopayments.com?subject=Interview%20Coach%20Support"
                className="inline-flex items-center justify-center rounded-xl border border-white/60 px-4 py-3 text-sm font-semibold text-white transition-transform duration-200 hover:-translate-y-0.5 hover:bg-white/10"
              >
                Email Billing Support
              </a>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
