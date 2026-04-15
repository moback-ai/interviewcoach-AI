import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FiUser, FiMenu, FiX, FiLogIn, FiLogOut } from 'react-icons/fi';
import ThemeToggle from './ThemeToggle';
import { useAuth } from '../contexts/AuthContext';
import { supabase } from '../supabaseClient';
import { trackEvents } from '../services/mixpanel';

function Navbar({ disableNavigation = false }) {
  const { user } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const dropdownRef = useRef(null);

  const handleLogout = async () => {
    if (disableNavigation) return; // Prevent logout during question generation
    
    // Capture user data BEFORE any auth state changes
    const currentUserId = user?.id;
    const currentUserEmail = user?.email;
    
    // Track sign out event with captured user data
    trackEvents.signOut({
      user_id: currentUserId,
      user_email: currentUserEmail,
      logout_timestamp: new Date().toISOString()
    });
    
    await supabase.auth.signOut();
    window.location.reload();
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Helper function to render navigation links
  const renderNavLink = (to, children, onClick = null) => {
    if (disableNavigation) {
      return (
        <span className="text-[var(--color-text-secondary)] cursor-not-allowed opacity-60">
          {children}
        </span>
      );
    }
    
    if (onClick) {
      return (
        <Link to={to} onClick={onClick} className="hover:text-[var(--color-accent)]">
          {children}
        </Link>
      );
    }
    
    return (
      <Link to={to} className="hover:text-[var(--color-accent)]">
        {children}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-50 bg-[var(--color-bg)] border-b border-[var(--color-border)]">
      <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 py-3 sm:py-4 flex items-center justify-between">
        {/* Logo */}
        {disableNavigation ? (
          <span className="text-lg sm:text-xl md:text-2xl font-bold text-[var(--color-text-secondary)] tracking-tight opacity-60 cursor-not-allowed">
            Interview<span className="text-[var(--color-text-secondary)]">Coach</span>
          </span>
        ) : (
          <Link to="/" className="text-lg sm:text-xl md:text-2xl font-bold text-[var(--color-primary)] tracking-tight hover:opacity-90 transition-opacity duration-200">
            Interview<span className="text-[var(--color-accent)]">Coach</span>
          </Link>
        )}

        {/* Desktop Nav */}
        <nav className="hidden md:flex space-x-4 lg:space-x-6 text-sm font-medium">
          {renderNavLink("/", "Home")}
          {user && renderNavLink("/dashboard", "Dashboard")}
          {renderNavLink("/upload", "Upload")}
          {renderNavLink("/faq", "Help & FAQ")}
          <span className="text-[var(--color-text-primary)] cursor-not-allowed">Contact</span>
        </nav>

        {/* Right side icons */}
        <div className="flex items-center space-x-2 sm:space-x-3 relative">
          {/* Theme Toggle */}
          <ThemeToggle />

          {/* Desktop User Icon */}
          {user ? (
            <div className="hidden md:block relative" ref={dropdownRef}>
              <button
                onClick={() => !disableNavigation && setDropdownOpen(!dropdownOpen)}
                disabled={disableNavigation}
                className={`w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full border-2 transition-all duration-200 ${
                  disableNavigation
                    ? 'border-[var(--color-text-secondary)] opacity-60 cursor-not-allowed'
                    : 'border-[var(--color-primary)] hover:bg-[var(--color-input-bg)] cursor-pointer'
                }`}
              >
                <FiUser size={18} color={disableNavigation ? "var(--color-text-secondary)" : "var(--color-text-primary)"} />
              </button>

              {dropdownOpen && !disableNavigation && (
                <div className="absolute right-0 mt-2 w-48 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl shadow-lg py-2 z-50">
                  <div className="px-4 py-2 text-sm text-[var(--color-text-primary)] font-medium">
                    {user.user_metadata.full_name || user.email}
                  </div>
                  <Link
                    to="/dashboard"
                    onClick={() => setDropdownOpen(false)}
                    className="block w-full text-left px-4 py-2 text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-input-bg)]"
                  >
                    Dashboard
                  </Link>
                  <Link
                    to="/profile"
                    onClick={() => setDropdownOpen(false)}
                    className="block w-full text-left px-4 py-2 text-sm text-[var(--color-text-primary)] hover:bg-[var(--color-input-bg)]"
                  >
                    Profile Settings
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-sm text-[var(--color-error)] hover:bg-[var(--color-input-bg)] rounded-b-md cursor-pointer"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          ) : (
            disableNavigation ? (
              <span className="hidden md:flex w-8 h-8 sm:w-9 sm:h-9 items-center justify-center rounded-full border text-[var(--color-text-secondary)] opacity-60 cursor-not-allowed">
                <FiLogIn size={18} />
              </span>
            ) : (
              <Link
                to="/signup"
                className="hidden md:flex w-8 h-8 sm:w-9 sm:h-9 items-center justify-center rounded-full border hover:bg-[var(--color-primary)] hover:text-white transition-all duration-200"
              >
                <FiLogIn size={18} />
              </Link>
            )
          )}

          {/* Hamburger Menu (mobile only) */}
          <button
            onClick={() => !disableNavigation && setMenuOpen(!menuOpen)}
            disabled={disableNavigation}
            className={`md:hidden w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-md border transition-all duration-200 ${
              disableNavigation
                ? 'text-[var(--color-text-secondary)] opacity-60 cursor-not-allowed'
                : 'cursor-pointer hover:bg-[var(--color-input-bg)]'
            }`}
            aria-label="Toggle Menu"
            aria-expanded={menuOpen}
          >
            {menuOpen ? <FiX size={18} /> : <FiMenu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {menuOpen && !disableNavigation && (
        <div className="md:hidden px-3 sm:px-4 md:px-6 pb-4 border-t border-[var(--color-border)]">
          <nav className="flex flex-col space-y-3 sm:space-y-4 text-sm font-medium pt-4">
            {renderNavLink("/", "Home", () => setMenuOpen(false))}
            {user && renderNavLink("/dashboard", "Dashboard", () => setMenuOpen(false))}
            {renderNavLink("/upload", "Upload", () => setMenuOpen(false))}
            {renderNavLink("/faq", "Help & FAQ", () => setMenuOpen(false))}
            <span className="text-[var(--color-text-primary)] cursor-not-allowed">Contact</span>

            {/* User Info (mobile only) */}
            {user ? (
              <div className="mt-4 border-t pt-4 border-[var(--color-border)] space-y-3">
                <div className="flex items-center space-x-2 text-[var(--color-text-primary)]">
                  <FiUser />
                  <span>{user.user_metadata.full_name || user.email}</span>
                </div>
                <Link
                  to="/dashboard"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center space-x-2 text-[var(--color-text-primary)] hover:underline"
                >
                  <FiUser />
                  <span>Dashboard</span>
                </Link>
                <Link
                  to="/profile"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center space-x-2 text-[var(--color-text-primary)] hover:underline"
                >
                  <FiUser />
                  <span>Profile Settings</span>
                </Link>
                <button
                  onClick={() => {
                    handleLogout();
                    setMenuOpen(false);
                  }}
                  className="flex items-center space-x-2 text-[var(--color-error)] hover:underline"
                >
                  <FiLogOut />
                  <span>Logout</span>
                </button>
              </div>
            ) : (
              <Link
                to="/signup"
                onClick={() => setMenuOpen(false)}
                className="mt-4 flex items-center space-x-2 px-4 py-2.5 border rounded-full text-sm font-medium hover:bg-[var(--color-primary)] hover:text-white transition-all duration-200"
              >
                <FiLogIn />
                <span>Login / Signup</span>
              </Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}

export default Navbar;
