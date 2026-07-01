import { motion, useReducedMotion } from 'framer-motion';
import AuthSceneBackdrop from './AuthSceneBackdrop';

const EASE_OUT = [0.22, 1, 0.36, 1];

export default function AuthSceneShell({
  variant = 'night',
  badge,
  icon,
  title,
  description,
  children,
  footer,
}) {
  const reduceMotion = useReducedMotion();

  return (
    <div className={`auth-scene-shell auth-scene-${variant}`}>
      <AuthSceneBackdrop variant={variant} />

      <motion.div
        className="auth-scene-panel-wrap"
        initial={reduceMotion ? false : { opacity: 0, y: 32, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.58, delay: reduceMotion ? 0 : 0.1, ease: EASE_OUT }}
      >
        <motion.section
          className="auth-scene-card"
          initial={reduceMotion ? false : { opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.48, delay: reduceMotion ? 0 : 0.2, ease: EASE_OUT }}
        >
          {(badge || icon || title || description) && (
            <header className="auth-scene-header">
              {(badge || icon) && (
                <motion.div
                  className="auth-scene-badge-wrap"
                  initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.42, delay: reduceMotion ? 0 : 0.26, ease: EASE_OUT }}
                >
                  {icon ? <span className="auth-scene-icon">{icon}</span> : null}
                  {badge ? <span className="auth-scene-badge">{badge}</span> : null}
                </motion.div>
              )}
              {title ? <h1 className="auth-scene-title">{title}</h1> : null}
              {description ? <p className="auth-scene-copy">{description}</p> : null}
            </header>
          )}

          <div className="auth-scene-content">{children}</div>
          {footer ? <div className="auth-scene-footer">{footer}</div> : null}
        </motion.section>
      </motion.div>
    </div>
  );
}
