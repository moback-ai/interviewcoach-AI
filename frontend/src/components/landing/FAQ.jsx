import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const faqs = [
  {
    question: "What is AI Interview Coach and how does it work?",
    answer:
      "AI Interview Coach is an intelligent interview preparation platform that uses artificial intelligence to conduct realistic mock interviews. Simply upload your resume and job description, and our AI generates personalized questions, conducts the interview with voice recognition, and provides detailed feedback on your performance.",
  },
  {
    question: "How does the AI personalize questions for my specific role?",
    answer:
      "Our AI analyzes your resume, skills, and experience alongside the job description to generate questions that are specifically tailored to your background and the role's requirements. This includes behavioral questions, technical questions, and situational scenarios relevant to your field.",
  },
  {
    question: "What types of roles and industries does this support?",
    answer:
      "We support interviews across all industries and roles - from software engineering and data science to marketing, sales, HR, finance, healthcare, and more. Our AI adapts to generate role-specific questions whether you're applying for technical positions, management roles, or creative positions.",
  },
  {
    question: "How realistic are the mock interviews?",
    answer:
      "Our interviews are highly realistic, featuring natural conversation flow, follow-up questions, and real-time analysis. The AI interviewer adapts to your responses, asks clarifying questions, and provides the same pressure and experience you'd encounter in actual interviews.",
  },
  {
    question: "What kind of feedback do I receive after the interview?",
    answer:
      "You receive comprehensive feedback including overall performance scores, communication analysis, technical knowledge assessment, and specific recommendations for improvement. The feedback covers strengths, areas for development, and actionable tips to enhance your interview skills.",
  },
  {
    question: "Can I practice multiple times with different questions?",
    answer:
      "Yes! You can generate multiple question sets for the same role, retake interviews with the same questions to improve, or upload different job descriptions to practice for various positions. Each session is tracked so you can monitor your progress over time.",
  },
  {
    question: "Is my data secure and private?",
    answer:
      "Absolutely. We use enterprise-grade security to protect your personal information, resume data, and interview recordings. Your data is encrypted and never shared with third parties. You have full control over your information and can delete it at any time.",
  },
  {
    question: "How much does it cost to use AI Interview Coach?",
    answer:
      "We offer flexible pricing options to suit different needs. You can start with a single interview session or choose from our subscription plans for unlimited practice. All plans include access to our full suite of features including personalized questions, detailed feedback, and progress tracking.",
  },
];

export default function FAQ() {
  const [openIndices, setOpenIndices] = useState([]);

  const toggle = (index) => {
    setOpenIndices((prev) =>
      prev.includes(index)
        ? prev.filter((i) => i !== index)
        : [...prev, index]
    );
  };

  return (
    <section className="py-16 sm:py-20 md:py-24 lg:py-28 px-3 sm:px-4 md:px-6 bg-[var(--color-bg)] transition-colors duration-300">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-center text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-text-primary)] mb-4 sm:mb-6">
          Frequently Asked Questions
        </h2>
        <p className="text-center text-sm sm:text-base md:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto mb-8 sm:mb-12 leading-relaxed">
          Everything you need to know about the platform, from features to support.
        </p>

        <div className="space-y-4 sm:space-y-5">
          {faqs.map((faq, index) => {
            const isOpen = openIndices.includes(index);
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.1 }}
                className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden"
              >
                <button
                  onClick={() => toggle(index)}
                  aria-expanded={isOpen}
                  className="w-full px-4 sm:px-6 py-4 sm:py-5 text-left flex items-center justify-between hover:bg-[var(--color-input-bg)] transition-colors duration-200"
                >
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base sm:text-lg font-semibold text-[var(--color-text-primary)] leading-relaxed">
                      {faq.question}
                    </h3>
                  </div>
                  <div className="flex items-center space-x-2 ml-4">
                    {isOpen ? (
                      <ChevronDown className="w-5 h-5 text-[var(--color-text-secondary)] flex-shrink-0 rotate-180 transition-transform duration-200" />
                    ) : (
                      <ChevronDown className="w-5 h-5 text-[var(--color-text-secondary)] flex-shrink-0 transition-transform duration-200" />
                    )}
                  </div>
                </button>

                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <div className="px-4 sm:px-6 pb-4 sm:pb-5 border-t border-[var(--color-border)]">
                        <div className="pt-4 sm:pt-5">
                          <p className="text-sm sm:text-base text-[var(--color-text-secondary)] leading-relaxed">
                            {faq.answer}
                          </p>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
