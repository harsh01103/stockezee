import { TrendingUp, Menu, X, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { Page } from '@/App';
import { useAuth } from '../context/AuthProvider';
import { LogoutButton } from './LogoutButton';

interface HeaderProps {
  currentPage: Page;
  onPageChange: (page: Page) => void;
}

const navItems = [
  { label: 'Home', page: 'home' },
  { label: 'Learner', page: 'learner' },
  {
    label: 'Demo', page: 'demo', isDropdown: true, subItems: [
      { label: 'Indian Market', page: 'demo' },
      { label: 'Commodities', page: 'demo-commodities' }
    ]
  },
  { label: 'Options', page: 'options' },
  { label: 'Research', page: 'research' },
  {
    label: 'News', page: 'news', isDropdown: true, subItems: [
      { label: 'Trading Suggestions', page: 'suggestions' },
      { label: 'Economic Calendar', page: 'calendar' },
      { label: 'Global & Stock News', page: 'stock-news' }
    ]
  },
  { label: 'About', page: 'about' },
  { label: 'Contact', page: 'contact' },
];

export function Header({ currentPage, onPageChange }: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user } = useAuth();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#050505]/95 backdrop-blur-md border-b border-[#333333]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-[72px]">
        <div className="flex items-center justify-between h-full">
          {/* Logo */}
          <button
            onClick={() => onPageChange('home')}
            className="flex items-center gap-2 group transition-transform duration-200 hover:scale-105"
          >
            <div className="w-8 h-8 bg-[#22c55e] rounded-lg flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">Study Stock</span>
          </button>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              if (item.isDropdown) {
                const isActive = item.subItems?.some(sub => currentPage === sub.page);
                return (
                  <div key={item.label} className="relative group">
                    <button
                      className={`flex items-center gap-1 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${isActive
                        ? 'text-[#22c55e] bg-[#22c55e]/10'
                        : 'text-[#94a3b8] hover:text-white hover:bg-white/5'
                        }`}
                    >
                      {item.label}
                      <ChevronDown className="w-4 h-4 transition-transform group-hover:rotate-180" />
                    </button>
                    {/* Dropdown Menu */}
                    <div className="absolute left-0 mt-1 w-56 bg-[#050505] border border-[#333333] rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 overflow-hidden z-50">
                      <div className="py-2">
                        {item.subItems?.map(sub => (
                          <button
                            key={sub.page}
                            onClick={() => onPageChange(sub.page as Page)}
                            className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${currentPage === sub.page ? 'text-[#22c55e] bg-[#22c55e]/10' : 'text-slate-300 hover:text-white hover:bg-white/5'}`}
                          >
                            {sub.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              }
              return (
                <button
                  key={item.page}
                  onClick={() => onPageChange(item.page as Page)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${currentPage === item.page
                    ? 'text-[#22c55e] bg-[#22c55e]/10'
                    : 'text-[#94a3b8] hover:text-white hover:bg-white/5'
                    }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Auth Buttons */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <>
                <Button
                  onClick={() => onPageChange('dashboard')}
                  className={`border-[#333333] ${currentPage === 'dashboard' ? 'bg-white/10 text-[#22c55e]' : 'text-white'} hover:bg-white/5`}
                  variant="outline"
                >
                  Dashboard
                </Button>
                <LogoutButton />
              </>
            ) : (
              <>
                <Button
                  onClick={() => onPageChange('login')}
                  variant="outline"
                  className="border-[#333333] text-white hover:bg-white/5 hover:border-[#4a5568]"
                >
                  Log in
                </Button>
                <Button
                  onClick={() => onPageChange('signup')}
                  className="bg-[#22c55e] hover:bg-[#16a34a] text-white"
                >
                  Sign Up
                </Button>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-white"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden absolute top-[72px] left-0 right-0 bg-[#0a0a0a] border-b border-[#333333] max-h-[calc(100vh-72px)] overflow-y-auto shadow-2xl">
          <nav className="px-4 py-4 space-y-2">
            {navItems.map((item) => {
              if (item.isDropdown) {
                return (
                  <div key={item.label} className="space-y-1">
                    <div className="px-4 py-2 text-xs font-bold text-slate-500 uppercase tracking-wider">{item.label}</div>
                    {item.subItems?.map(sub => (
                      <button
                        key={sub.page}
                        onClick={() => {
                          onPageChange(sub.page as Page);
                          setMobileMenuOpen(false);
                        }}
                        className={`block w-full text-left pl-8 pr-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${currentPage === sub.page
                          ? 'text-[#22c55e] bg-[#22c55e]/10'
                          : 'text-[#94a3b8] hover:text-white hover:bg-white/5'
                          }`}
                      >
                        {sub.label}
                      </button>
                    ))}
                  </div>
                );
              }

              return (
                <button
                  key={item.page}
                  onClick={() => {
                    onPageChange(item.page as Page);
                    setMobileMenuOpen(false);
                  }}
                  className={`block w-full text-left px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${currentPage === item.page
                    ? 'text-[#22c55e] bg-[#22c55e]/10'
                    : 'text-[#94a3b8] hover:text-white hover:bg-white/5'
                    }`}
                >
                  {item.label}
                </button>
              );
            })}
            <div className="pt-4 border-t border-[#333333] space-y-2">
              {user ? (
                <>
                  <Button
                    onClick={() => { onPageChange('dashboard'); setMobileMenuOpen(false); }}
                    variant="outline"
                    className="w-full border-[#333333] text-white hover:bg-white/5"
                  >
                    Dashboard
                  </Button>
                  <div className="flex justify-center w-full pt-2">
                    <LogoutButton />
                  </div>
                </>
              ) : (
                <>
                  <Button
                    onClick={() => { onPageChange('login'); setMobileMenuOpen(false); }}
                    variant="outline"
                    className="w-full border-[#333333] text-white hover:bg-white/5"
                  >
                    Log in
                  </Button>
                  <Button
                    onClick={() => { onPageChange('signup'); setMobileMenuOpen(false); }}
                    className="w-full bg-[#22c55e] hover:bg-[#16a34a] text-white"
                  >
                    Sign Up
                  </Button>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
