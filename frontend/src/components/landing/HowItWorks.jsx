import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUpTrayIcon,
  MagnifyingGlassIcon,
  SparklesIcon,
  PlayCircleIcon,
} from "@heroicons/react/24/outline";
import { useTheme } from "../../hooks/useTheme"; // adjust path as needed


const steps = [
  {
    icon: ArrowUpTrayIcon,
    title: "Upload Resume",
    desc: "Easily upload your resume and job description for smart analysis.",
    imageLight: "/assets/landing/steps/upload-light.png",
    imageDark: "/assets/landing/steps/upload-dark.png",
  },
  {
    icon: MagnifyingGlassIcon,
    title: "Analyze Fit",
    desc: "We match your skills with the job description using AI models.",
    imageLight: "/assets/landing/steps/step2_light.png",
    imageDark: "/assets/landing/steps/step2_dark.png",
  },
  {
    icon: SparklesIcon,
    title: "Generate Q&A",
    desc: "Get tailored interview questions and answers to prepare smartly.",
    imageLight: "/assets/landing/steps/step3_light.png",
    imageDark: "/assets/landing/steps/step3_dark.png",
  },
  {
    icon: PlayCircleIcon,
    title: "Mock Interview",
    desc: "Practice in a realistic, AI-powered interview environment.",
    imageLight: "/assets/landing/steps/step4_light.png",
    imageDark: "/assets/landing/steps/step4_dark.png",
  },
];

export default function HowItWorks() {
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { isDark } = useTheme();

  const [themeChanged, setThemeChanged] = useState(0);

    useEffect(() => {
    const handleThemeChange = () => setThemeChanged(prev => prev + 1);
    window.addEventListener("theme-change", handleThemeChange);
    return () => window.removeEventListener("theme-change", handleThemeChange);
    }, []);



  const activeIndex = hoveredIndex !== null ? hoveredIndex : selectedIndex;

  return (
    <section className="relative py-16 sm:py-20 md:py-24 lg:py-28 px-3 sm:px-4 md:px-6 bg-[linear-gradient(135deg,var(--color-bg),rgba(0,0,0,0.015))] overflow-hidden transition-colors">
      {/* Glow Background */}
      <div className="absolute inset-0 pointer-events-none -z-10">
        <div className="absolute w-[70vw] h-[70vw] top-[-20%] left-[-10%] bg-[radial-gradient(circle,var(--color-primary)_0%,transparent_70%)] blur-3xl opacity-10" />
      </div>

      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row gap-8 sm:gap-10 md:gap-12 items-center">
        {/* Left: Steps */}
        <div className="flex-1">
          <div className="text-center md:text-left mb-8 sm:mb-10 md:mb-12">
            <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-text-primary)]">
              Land Your Dream Job in 4 Smart Steps
            </h2>
            <p className="mt-3 sm:mt-4 text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto md:mx-0 leading-relaxed">
              Upload your resume, get matched with job descriptions, and practice real-time interviews with AI — it's your edge in today's job market.
            </p>
          </div>

          <div className="relative space-y-8 sm:space-y-12 md:space-y-16 border-l-[3px] border-dashed border-[var(--color-border)] pl-6 sm:pl-8 md:pl-10 before:absolute before:top-0 before:left-[6px] sm:before:left-[8px] before:h-full before:w-[3px] before:bg-gradient-to-b before:from-[var(--color-primary)] before:to-transparent before:rounded-full">
            {steps.map(({ icon: Icon, title, desc, imageLight, imageDark }, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.15 }}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => {
                  setHoveredIndex(null);
                  setSelectedIndex(index);
                }}
                className="relative group"
              >
                {/* Glowing Dot */}
                <div className="absolute -left-[18px] sm:-left-[20px] md:-left-[24px] top-2 w-4 h-4 sm:w-5 sm:h-5 bg-[var(--color-primary)] rounded-full shadow-lg shadow-[var(--color-primary)] group-hover:scale-110 transition-transform" />

                {/* Step Card */}
                <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-4 sm:p-5 md:p-6 lg:p-7 rounded-2xl shadow-xl hover:shadow-2xl hover:scale-[1.02] transition duration-300">
                  <div className="flex items-center gap-3 sm:gap-4 mb-3 sm:mb-4">
                    <div className="p-2 sm:p-3 rounded-2xl bg-gradient-to-br from-[var(--color-primary)] to-[var(--color-accent)] shadow-md">
                      <Icon className="h-5 w-5 sm:h-6 sm:w-6 md:h-7 md:w-7 text-white" />
                    </div>
                    <h3 className="text-lg sm:text-xl md:text-2xl font-semibold text-[var(--color-text-primary)]">
                      {title}
                    </h3>
                  </div>
                  <p className="text-[var(--color-text-secondary)] text-xs sm:text-sm md:text-base leading-relaxed">
                    {desc}
                  </p>

                    {/* Mobile-only image */}
                    <div className="mt-4 sm:mt-6 block lg:hidden">
                      <img
                        src={isDark ? imageDark : imageLight}
                        alt={title}
                        className="w-full max-w-lg rounded-2xl shadow border border-[var(--color-border)]"
                      />
                    </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Right: Desktop-only image */}
{/* Right: Desktop-only image */}
<div className="hidden lg:flex flex-1 items-center justify-center">
  <AnimatePresence mode="wait">
    <motion.div
      key={`${activeIndex}-${isDark ? "dark" : "light"}-${themeChanged}`}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="w-full max-w-3xl px-4" // <- updated width
    >
      <img
        src={isDark ? steps[activeIndex].imageDark : steps[activeIndex].imageLight}
        alt={steps[activeIndex].title}
        className="w-full h-auto rounded-2xl shadow-xl border border-[var(--color-primary)]"
      />
    </motion.div>
  </AnimatePresence>
</div>

      </div>
    </section>
  );
}
