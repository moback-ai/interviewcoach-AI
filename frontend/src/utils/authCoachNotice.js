const buildNoticeId = () => `auth-coach-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const createAuthCoachNotice = ({
  kind = 'event',
  tone = 'info',
  title = '',
  message = '',
  actionLabel = '',
  actionHref = '',
} = {}) => ({
  id: buildNoticeId(),
  kind,
  tone,
  title,
  message,
  actionLabel,
  actionHref,
});

export const getDefaultLoginCoachNotice = () => createAuthCoachNotice({
  kind: 'default',
  tone: 'info',
  title: 'Live access status',
  message: 'Sign in to continue. Verification, password reset, and account recovery updates will appear here when they are ready.',
});

export const buildLoginCoachState = ({
  identifier = '',
  notice,
} = {}) => {
  const normalizedIdentifier = typeof identifier === 'string' ? identifier.trim() : '';
  const state = {};

  if (normalizedIdentifier) {
    state.prefillIdentifier = normalizedIdentifier;
  }

  if (notice?.message) {
    state.authNotice = createAuthCoachNotice(notice);
  }

  return state;
};
