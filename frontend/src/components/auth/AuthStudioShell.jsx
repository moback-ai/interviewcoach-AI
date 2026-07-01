import { motion, useReducedMotion } from 'framer-motion';
import AuthSceneBackdrop from './AuthSceneBackdrop';

const EASE_OUT = [0.22, 1, 0.36, 1];

const heroContainer = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.09,
      delayChildren: 0.12,
    },
  },
};

const heroItem = {
  hidden: { opacity: 0, x: -20 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.5, ease: EASE_OUT },
  },
};

const heroList = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.36,
    },
  },
};

const heroPointItem = {
  hidden: { opacity: 0, x: -14 },
  show: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.42, ease: EASE_OUT },
  },
};

export default function AuthStudioShell({
  eyebrow,
  title,
  description,
  wide = false,
  children,
  footer,
  heroTitle = 'Practice interviews with confidence.',
  heroCopy = 'Tailored questions from your resume and job description, plus voice-led mock sessions and instant feedback.',
}) {
  const reduceMotion = useReducedMotion();

  const heroPoints = [
    'Resume-aware question sets',
    'Voice mock interviews',
    'Actionable feedback',
  ];

  return (
    <div className="auth-studio-page">
      <AuthSceneBackdrop variant="night" className="auth-studio-page-backdrop" />

      <motion.aside
        className="auth-studio-hero"
        initial={reduceMotion ? false : { opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: EASE_OUT }}
      >
        <div className="auth-studio-hero-backdrop">
          <div className="auth-studio-hero-shade" />
          <div className="auth-studio-hero-grid" />
        </div>
        <motion.div
          className="auth-studio-hero-content"
          variants={reduceMotion ? undefined : heroContainer}
          initial={reduceMotion ? false : 'hidden'}
          animate="show"
        >
          <motion.p className="auth-studio-hero-kicker" variants={reduceMotion ? undefined : heroItem}>
            InterviewCoach
          </motion.p>
          <motion.h2 className="auth-studio-hero-title" variants={reduceMotion ? undefined : heroItem}>
            {heroTitle}
          </motion.h2>
          <motion.p className="auth-studio-hero-copy" variants={reduceMotion ? undefined : heroItem}>
            {heroCopy}
          </motion.p>
          <motion.ul
            className="auth-studio-hero-points"
            variants={reduceMotion ? undefined : heroList}
          >
            {heroPoints.map((point) => (
              <motion.li key={point} variants={reduceMotion ? undefined : heroPointItem}>
                {point}
              </motion.li>
            ))}
          </motion.ul>
        </motion.div>
      </motion.aside>

      <motion.div
        className="auth-studio-panel"
        initial={reduceMotion ? false : { opacity: 0, y: 28, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.62, delay: reduceMotion ? 0 : 0.18, ease: EASE_OUT }}
      >
        <motion.section
          className={`auth-studio-card ${wide ? 'auth-studio-card-wide' : ''}`}
          initial={reduceMotion ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: reduceMotion ? 0 : 0.28, ease: EASE_OUT }}
        >
          <header className="auth-studio-header">
            {eyebrow ? <p className="auth-studio-eyebrow">{eyebrow}</p> : null}
            {title ? <h1 className="auth-studio-title">{title}</h1> : null}
            {description ? <p className="auth-studio-copy">{description}</p> : null}
          </header>
          <div className="auth-studio-content">{children}</div>
          {footer ? <div className="auth-studio-footer">{footer}</div> : null}
        </motion.section>
      </motion.div>
    </div>
  );
}
