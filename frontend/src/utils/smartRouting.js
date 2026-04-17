// Smart routing based on user state
export async function performSmartRedirect(user, navigate) {
  if (typeof user === 'function' && !navigate) {
    navigate = user;
    user = true;
  }
  if (!user) { navigate('/login'); return; }
  navigate('/dashboard');
}
