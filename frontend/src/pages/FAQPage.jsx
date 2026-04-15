import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, 
  ChevronDown, 
  ChevronUp, 
  HelpCircle, 
  FileText, 
  Upload, 
  PlayCircle, 
  BarChart3, 
  CreditCard, 
  Settings,
  Wifi,
  MessageSquare
} from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import Navbar from '../components/Navbar';

// FAQ Data extracted from support_bot.md
const faqData = [
  {
    category: 'Getting Started',
    icon: HelpCircle,
    color: 'text-blue-500',
    questions: [
      {
        question: 'What is AI Interview Coach?',
        answer: 'AI Interview Coach is an intelligent interview preparation platform that helps you practice for job interviews using artificial intelligence. It provides AI-powered interviews, real-time feedback, resume analysis, and comprehensive performance reports.'
      },
      {
        question: 'How do I create an account?',
        answer: 'You can create an account by visiting the sign-up page and choosing either email/password registration or signing up with your Google account. Complete your profile with your full name and verify your email address.'
      }
    ]
  },
  {
    category: 'File Uploads',
    icon: Upload,
    color: 'text-green-500',
    questions: [
      {
        question: 'What file formats are supported for resume upload?',
        answer: 'We support PDF files (.pdf), Microsoft Word documents (.doc, .docx), and text files (.txt). Keep file sizes under 10MB for best results.',
      },
      {
        question: 'What file formats are supported for job descriptions?',
        answer: 'Job descriptions can be uploaded as PDF files (.pdf), Microsoft Word documents (.doc, .docx), or text files (.txt).',
      },
      {
        question: 'Do I need to upload job description or resume first?',
        answer: 'Upload your job description first, then your resume. This order helps the AI better understand the role requirements and match your qualifications accordingly.',
      }
    ]
  },
  {
    category: 'Interview Process',
    icon: PlayCircle,
    color: 'text-purple-500',
    questions: [
      {
        question: 'How does the interview process work?',
        answer: 'The interview includes an opening introduction, question presentation with audio narration, your response time, real-time analysis, follow-up questions, and concludes with immediate feedback and detailed recommendations.',
      },
      {
        question: 'What types of questions will I be asked?',
        answer: 'You\'ll encounter behavioral questions (situational examples), technical questions (role-specific knowledge), and situational questions (problem-solving scenarios).',
      },
      {
        question: 'How do I review generated questions before the interview?',
        answer: 'After uploading your documents, you\'ll see all generated questions with 3 difficulty levels (beginner, intermediate, advanced) and sample answers. Take time to read through them and prepare your own responses.',
      }
    ]
  },
  {
    category: 'Feedback & Results',
    icon: BarChart3,
    color: 'text-orange-500',
    questions: [
      {
        question: 'How do I view my interview feedback?',
        answer: 'Go to your dashboard, find your completed interview in the "Interview History" section, and click on it to view comprehensive feedback including overall scores, strengths, areas for improvement, and question-by-question analysis.',
      },
      {
        question: 'What do the performance scores mean?',
        answer: 'Scores are rated on a 10-point scale: 8-10/10 (Excellent - strong, well-structured responses), 6-7/10 (Good - solid with room for improvement), below 6/10 (Needs Improvement - lacks structure or relevance).',
      }
    ]
  },
  {
    category: 'Payments',
    icon: CreditCard,
    color: 'text-red-500',
    questions: [
      {
        question: 'What payment methods are accepted?',
        answer: 'We accept credit cards (Visa, MasterCard, American Express), debit cards, UPI QR codes, and UPI IDs. All payments are processed securely with industry-standard encryption.',
      },
      {
        question: 'How do I view my payment history?',
        answer: 'Log into your account, go to your profile settings, and click on the "Payments History" tab to view all your transactions with dates, amounts, payment methods, and status.',
      },
      {
        question: 'What if my payment fails?',
        answer: 'Check that your card information is correct, ensure sufficient funds, contact your bank if issues persist, or try a different payment method. Contact support@dodopayments.com for payment-related queries.',
      }
    ]
  },
  {
    category: 'Technical Issues',
    icon: Wifi,
    color: 'text-gray-500',
    questions: [
      {
        question: 'What should I do if my interview gets interrupted?',
        answer: 'Don\'t panic - most interruptions can be resolved quickly. Check your internet connection, refresh the browser, restart audio/video equipment, and log back in. The system automatically saves your progress.',
      },
      {
        question: 'What are the technical requirements?',
        answer: 'You need a stable internet connection, working microphone, modern browser (Chrome, Firefox, Safari, or Edge), and optionally a webcam. Test your equipment before starting the interview.',
      },
      {
        question: 'How do I retake an interview?',
        answer: 'Access your dashboard to retake interviews. You can retake with the same questions, generate new questions (Set 2), or upload new files for a completely different interview experience.',
      }
    ]
  },
  {
    category: 'Account Management',
    icon: Settings,
    color: 'text-indigo-500',
    questions: [
      {
        question: 'How do I contact support?',
        answer: 'You can contact support through the contact form on the website, send an email to support, or use the self-help resources including FAQ sections and troubleshooting guides.',
      },
      {
        question: 'Can I update my profile information?',
        answer: 'Yes, you can update your profile information anytime from your account settings. This includes your full name, email address, and other profile details.',
      }
    ]
  }
];

function FAQPage() {
  const { isDark } = useTheme();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [expandedItems, setExpandedItems] = useState({});

  // Filter FAQs based on search term and category
  const filteredFAQs = useMemo(() => {
    let filtered = faqData;

    // Filter by category
    if (selectedCategory !== 'All') {
      filtered = filtered.filter(category => category.category === selectedCategory);
    }

    // Filter by search term
    if (searchTerm.trim()) {
      filtered = filtered.map(category => ({
        ...category,
        questions: category.questions.filter(q => 
          q.question.toLowerCase().includes(searchTerm.toLowerCase()) ||
          q.answer.toLowerCase().includes(searchTerm.toLowerCase())
        )
      })).filter(category => category.questions.length > 0);
    }

    return filtered;
  }, [searchTerm, selectedCategory]);

  const toggleExpanded = (categoryIndex, questionIndex) => {
    const key = `${categoryIndex}-${questionIndex}`;
    setExpandedItems(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const categories = ['All', ...faqData.map(cat => cat.category)];

  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-[var(--color-bg)]">
        <div className="max-w-6xl mx-auto px-3 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="text-center mb-6 sm:mb-8 md:mb-10 lg:mb-12"
          >
            <h1 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tight text-[var(--color-primary)] mb-3 sm:mb-4">
              Frequently Asked Questions
            </h1>
            <p className="text-xs sm:text-sm md:text-base lg:text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto leading-relaxed px-2 sm:px-4 mb-4 sm:mb-6">
              Find quick answers to common questions about AI Interview Coach. 
              Can't find what you're looking for? <a href="#contact" className="text-[var(--color-primary)] hover:underline">Contact our support team</a>.
            </p>
          </motion.div>

          {/* Search Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="mb-6 sm:mb-8 md:mb-10"
          >
            <div className="relative max-w-xs sm:max-w-md md:max-w-2xl mx-auto px-2 sm:px-0">
              <Search className="absolute left-3 sm:left-4 top-1/2 transform -translate-y-1/2 text-[var(--color-text-secondary)] w-4 h-4 sm:w-5 sm:h-5" />
              <input
                type="text"
                placeholder="Search FAQs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 sm:pl-12 pr-3 sm:pr-4 py-3 sm:py-4 text-sm sm:text-base rounded-lg sm:rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-text-primary)] placeholder-[var(--color-text-secondary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent"
              />
            </div>
          </motion.div>

          {/* Category Filter */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mb-6 sm:mb-8 md:mb-10"
          >
            <div className="flex flex-wrap justify-center gap-2 sm:gap-3 px-2 sm:px-0">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-3 sm:px-4 py-2 sm:py-2.5 rounded-full text-xs sm:text-sm font-medium transition-all duration-200 ${
                    selectedCategory === category
                      ? 'bg-[var(--color-primary)] text-white shadow-md'
                      : 'bg-[var(--color-card)] text-[var(--color-text-primary)] border border-[var(--color-border)] hover:bg-[var(--color-input-bg)] hover:shadow-sm'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </motion.div>

           {/* FAQ Content */}
           <motion.div
             initial={{ opacity: 0 }}
             animate={{ opacity: 1 }}
             transition={{ duration: 0.5, delay: 0.3 }}
             className="space-y-4 sm:space-y-6 md:space-y-8"
           >
             <AnimatePresence>
               {filteredFAQs.map((category, categoryIndex) => (
                 <motion.div
                   key={category.category}
                   initial={{ opacity: 0, y: 20 }}
                   animate={{ opacity: 1, y: 0 }}
                   exit={{ opacity: 0, y: -20 }}
                   transition={{ duration: 0.3 }}
                   className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] shadow-lg hover:shadow-xl transition-all duration-300"
                 >
                   {/* Category Header - Similar to DashboardPage pairing headers */}
                   <div className="p-3 sm:p-4 md:p-6 border-b border-[var(--color-border)]">
                     <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                       <div className="flex items-center space-x-2 sm:space-x-3">
                         <category.icon className={`w-4 h-4 sm:w-5 sm:h-5 ${category.color}`} />
                         <h2 className="text-base sm:text-lg md:text-xl font-semibold text-[var(--color-text-primary)]">
                           {category.category}
                         </h2>
                       </div>
                       <span className="text-xs sm:text-sm text-[var(--color-text-secondary)] bg-[var(--color-input-bg)] px-2 sm:px-3 py-1 rounded-full self-start sm:self-auto">
                         {category.questions.length} questions
                       </span>
                     </div>
                   </div>

                   {/* Questions Container - Similar to DashboardPage question sets */}
                   <div className="p-3 sm:p-4 md:p-6">
                     <div className="space-y-3 sm:space-y-4 md:space-y-5">
                       {category.questions.map((faq, questionIndex) => {
                         const isExpanded = expandedItems[`${categoryIndex}-${questionIndex}`];
                         return (
                           <motion.div
                             key={questionIndex}
                             initial={{ opacity: 0 }}
                             animate={{ opacity: 1 }}
                             transition={{ duration: 0.2, delay: questionIndex * 0.1 }}
                             className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg sm:rounded-xl md:rounded-2xl overflow-hidden shadow-sm hover:shadow-lg transition-all duration-300"
                           >
                             <button
                               onClick={() => toggleExpanded(categoryIndex, questionIndex)}
                               className="w-full px-3 sm:px-4 md:px-6 py-3 sm:py-4 md:py-5 text-left flex items-center justify-between hover:bg-[var(--color-input-bg)] transition-colors duration-200"
                             >
                               <div className="flex-1 min-w-0">
                                 <h3 className="text-sm sm:text-base md:text-lg font-semibold text-[var(--color-text-primary)] leading-relaxed">
                                   {faq.question}
                                 </h3>
                               </div>
                               <div className="flex items-center space-x-2 ml-2 sm:ml-4">
                                 {isExpanded ? (
                                   <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5 text-[var(--color-text-secondary)] flex-shrink-0" />
                                 ) : (
                                   <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5 text-[var(--color-text-secondary)] flex-shrink-0" />
                                 )}
                               </div>
                             </button>
                             
                             <AnimatePresence>
                               {isExpanded && (
                                 <motion.div
                                   initial={{ height: 0, opacity: 0 }}
                                   animate={{ height: 'auto', opacity: 1 }}
                                   exit={{ height: 0, opacity: 0 }}
                                   transition={{ duration: 0.3 }}
                                   className="overflow-hidden"
                                 >
                                     <div className="px-3 sm:px-4 md:px-6 pb-3 sm:pb-4 md:pb-5 border-t border-[var(--color-border)]">
                                       <div className="pt-3 sm:pt-4 md:pt-5">
                                         <p className="text-xs sm:text-sm md:text-base text-[var(--color-text-secondary)] leading-relaxed">
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
                 </motion.div>
               ))}
             </AnimatePresence>

            {/* No Results */}
            {filteredFAQs.length === 0 && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-center py-12"
              >
                <MessageSquare className="w-16 h-16 text-[var(--color-text-secondary)] mx-auto mb-4" />
                <h3 className="text-xl font-medium text-[var(--color-text-primary)] mb-2">
                  No FAQs found
                </h3>
                <p className="text-[var(--color-text-secondary)] mb-6">
                  Try adjusting your search terms or browse all categories.
                </p>
                <button
                  onClick={() => {
                    setSearchTerm('');
                    setSelectedCategory('All');
                  }}
                  className="px-6 py-3 bg-[var(--color-primary)] text-white rounded-lg hover:opacity-90 transition-opacity"
                >
                  Clear Filters
                </button>
              </motion.div>
            )}
          </motion.div>

          {/* Contact Support Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="mt-12 sm:mt-16 md:mt-20 text-center"
          >
            <div className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl sm:rounded-2xl shadow-lg hover:shadow-xl transition-all duration-300 p-4 sm:p-6 md:p-8">
              <h2 className="text-lg sm:text-xl md:text-2xl font-bold text-[var(--color-text-primary)] mb-3 sm:mb-4">
                Still need help?
              </h2>
              <p className="text-xs sm:text-sm md:text-base text-[var(--color-text-secondary)] mb-4 sm:mb-6 max-w-2xl mx-auto leading-relaxed px-2">
                Can't find the answer you're looking for? Our support team is here to help you with any questions or issues.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
                <button className="px-4 sm:px-6 py-2.5 sm:py-3 text-sm sm:text-base font-medium bg-[var(--color-primary)] text-white rounded-lg sm:rounded-xl hover:opacity-90 transition-all duration-200 shadow-md hover:shadow-lg">
                  Contact Support
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </>
  );
}

export default FAQPage;
