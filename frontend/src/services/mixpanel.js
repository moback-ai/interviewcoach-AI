// Mixpanel removed — keep a compatible no-op interface so page code does not crash.
const noop = () => {};

export const trackEvents = {
  track: noop,
  identify: noop,
  reset: noop,
  landingPageVisit: noop,
  signUp: noop,
  signIn: noop,
  signOut: noop,
  resumeUploaded: noop,
  jobDescriptionSaved: noop,
  questionsGenerated: noop,
  questionsRegenerated: noop,
  questionsAccessed: noop,
  paymentPage: noop,
  participatedInMockInterview: noop,
  mockInterviewFeedbackGenerated: noop,
  interviewFeedbackAccessed: noop,
};

export default trackEvents;
