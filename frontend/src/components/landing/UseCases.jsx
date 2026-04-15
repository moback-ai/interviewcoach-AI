// src/components/landing/UseCases.jsx
import { GraduationCap, Briefcase, User } from "lucide-react";
import { motion } from "framer-motion";

const useCases = [
  {
    icon: <GraduationCap className="w-6 h-6 text-white" />,
    title: "Students & Graduates",
    desc: "Master internship and campus interviews with role-specific mock sessions and resume-tailored guidance.",
  },
  {
    icon: <Briefcase className="w-6 h-6 text-white" />,
    title: "Active Job Seekers",
    desc: "Target your dream job with position-matched interview practice, recruiter-style screening, and AI coaching.",
  },
  {
    icon: <User className="w-6 h-6 text-white" />,
    title: "Working Professionals",
    desc: "Ace role transitions, promotions, or domain shifts through personalized mock interviews and performance analytics.",
  },
];

export default function UseCases() {
  return (
    <section className="relative overflow-hidden py-16 sm:py-20 md:py-24 px-3 sm:px-4 md:px-6 lg:px-8 bg-[linear-gradient(135deg,var(--color-bg),rgba(0,0,0,0.02))] transition-colors">
      {/* Subtle Glow Effect */}
      <div className="absolute inset-0 -z-10 pointer-events-none">
        <div className="absolute w-[50vw] h-[50vw] bottom-[-20%] right-[-15%] bg-[radial-gradient(circle,var(--color-primary)_0%,transparent_70%)] blur-3xl opacity-10" />
      </div>

      <div className="max-w-7xl mx-auto text-center">
        <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold text-[var(--color-text-primary)] tracking-tight mb-4 sm:mb-6">
          Tailored to Every Ambition
        </h2>
        <p className="text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto mb-8 sm:mb-12 md:mb-16 leading-relaxed">
          Whether you're entering the workforce or aiming for your next big role, Interview Coach adapts to your journey and goals.
        </p>

        <div className="grid gap-6 sm:gap-8 md:gap-10 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {useCases.map((useCase, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 40 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-3xl p-4 sm:p-6 md:p-8 text-left shadow-xl hover:shadow-2xl hover:scale-[1.015] transition-all duration-300 backdrop-blur-md bg-opacity-80"
            >
              <div className="flex items-center gap-3 sm:gap-4 mb-3 sm:mb-4 md:mb-5">
                <div className="p-2 sm:p-3 rounded-2xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] shadow-md">
                  {useCase.icon}
                </div>
                <h3 className="text-lg sm:text-xl font-semibold text-[var(--color-text-primary)]">
                  {useCase.title}
                </h3>
              </div>
              <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed">
                {useCase.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
