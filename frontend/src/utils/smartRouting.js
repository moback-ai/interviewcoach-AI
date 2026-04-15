// Smart routing based on user state
export async function performSmartRedirect(user, navigate) {
  if (!user) { navigate('/login'); return; }
  navigate('/dashboard');
}
