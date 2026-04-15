import React from 'react';
import {
  LightBulbIcon,
  ClipboardDocumentCheckIcon,
  ChatBubbleBottomCenterTextIcon,
  MicrophoneIcon,
} from '@heroicons/react/24/outline';
import { motion } from 'framer-motion';

const features = [
  {
    title: 'Smart Resume Parsing',
    description: 'Instantly analyze your resume and extract key information.',
    icon: ClipboardDocumentCheckIcon,
  },
  {
    title: 'Job Matching AI',
    description: 'Compare your resume to job descriptions using AI.',
    icon: LightBulbIcon,
  },
  {
    title: 'Custom Questions',
    description: 'Receive tailored interview questions based on your skills.',
    icon: ChatBubbleBottomCenterTextIcon,
  },
  {
    title: 'Mock Interviews',
    description: 'Practice with real-time AI-generated interviews.',
    icon: MicrophoneIcon,
  },
];

const containerVariants = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.15,
    },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: 'easeOut' } },
};

export default function FeatureHighlights() {
  return (
    <section
      className="relative py-16 sm:py-20 md:py-24 lg:py-28 transition-colors overflow-hidden"
      style={{
        background: "linear-gradient(135deg, var(--color-bg), rgba(255,255,255,0.04))",
      }}
    >

      <div className="relative max-w-6xl mx-auto px-3 sm:px-4 md:px-6 z-10">
<motion.h2
  initial={{ opacity: 0, y: 20 }}
  whileInView={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.6, ease: 'easeOut' }}
  viewport={{ once: true }}
  className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-center mb-8 sm:mb-12 md:mb-16 text-[var(--color-text-primary)]"
>
  Everything You Need to Ace Your Interview
</motion.h2>


        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="grid gap-6 sm:gap-8 md:gap-10 grid-cols-1 md:grid-cols-2"
        >
          {features.map(({ title, description, icon: Icon }, index) => (
            <motion.div
              key={index}
              variants={cardVariants}
              className="group bg-[var(--color-card)] border border-[var(--color-border)] rounded-2xl p-4 sm:p-6 md:p-8 shadow-xl hover:shadow-2xl transition-all duration-300 hover:-translate-y-1"
            >
              {/* Icon Glow */}
            <div className="p-2 sm:p-3 rounded-2xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] shadow-md mb-4 sm:mb-6 w-fit">
              <Icon className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
            </div>


              {/* Title */}
              <h3 className="text-lg sm:text-xl font-semibold mb-2 sm:mb-3 text-[var(--color-text-primary)]">
                {title}
              </h3>

              {/* Description */}
              <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed">
                {description}
              </p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
