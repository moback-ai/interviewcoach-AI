// Mixpanel removed — no-op shim
export const trackEvents = { track: () => {}, identify: () => {}, reset: () => {} };
export default trackEvents;
