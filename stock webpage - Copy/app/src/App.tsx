import { useState, useEffect, lazy, Suspense } from 'react';
import { Header } from './components/Header';
import { HomePage } from './pages/HomePage';
import { LearnerPage } from './pages/LearnerPage';
import DemoTrading from './pages/DemoTrading';
import DemoCommoditiesTrading from './pages/DemoCommoditiesTrading';
import { AboutPage } from './pages/AboutPage';
import { ContactPage } from './pages/ContactPage';
import { NewsPage } from './pages/NewsPage';
import { TradingSuggestionPage } from './pages/TradingSuggestionPage';

import { EconomicCalendarPage } from './pages/EconomicCalendarPage';
import { GeneralNewsPage } from './pages/GeneralNewsPage';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { ReplayPage } from './pages/ReplayPage';
import { ResearchPage } from './pages/ResearchPage';

const OptionsPage = lazy(() =>
  import('./pages/OptionsPage').then((module) => ({ default: module.OptionsPage }))
);

export type Page = 'home' | 'learner' | 'demo' | 'demo-commodities' | 'options' | 'about' | 'contact' | 'news' | 'calendar' | 'stock-news' | 'login' | 'signup' | 'dashboard' | 'suggestions' | 'replay' | 'research';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>(() => {
    const saved = localStorage.getItem('currentPage');
    return (saved as Page) || 'home';
  });

  useEffect(() => {
    // Basic Hash/URL-like routing reaction for magic link redirects back from email
    if (window.location.hash.includes('access_token')) {
      setCurrentPage('dashboard');
    }
  }, []);



  useEffect(() => {
    localStorage.setItem('currentPage', currentPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [currentPage]);

  return (
    <div className="min-h-screen bg-[#050505] text-white overflow-hidden relative">
      <div className="bg-red-500/20 border-b border-red-500/50 text-red-200 text-[10px] font-black uppercase tracking-[0.2em] text-center py-1.5 z-50 relative flex items-center justify-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
        SYSTEM IN SIMULATION MODE. LIVE EXECUTION DISABLED.
      </div>
      <Header currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="relative z-10 pt-[72px]">
        {currentPage === 'home' && <HomePage onPageChange={setCurrentPage} />}
        {currentPage === 'learner' && <LearnerPage />}
        {currentPage === 'demo' && <DemoTrading />}
        {currentPage === 'demo-commodities' && <DemoCommoditiesTrading />}
        {currentPage === 'options' && (
          <Suspense fallback={<div className="min-h-[60vh] animate-pulse bg-[#050505]" />}>
            <OptionsPage />
          </Suspense>
        )}
        {currentPage === 'about' && <AboutPage onPageChange={setCurrentPage} />}
        {currentPage === 'contact' && <ContactPage />}
        {currentPage === 'news' && <NewsPage onPageChange={setCurrentPage} />}
        {currentPage === 'suggestions' && <TradingSuggestionPage onPageChange={setCurrentPage} />}
        {currentPage === 'calendar' && <EconomicCalendarPage />}
        {currentPage === 'stock-news' && <GeneralNewsPage />}
        {currentPage === 'login' && <LoginPage onPageChange={setCurrentPage} />}
        {currentPage === 'signup' && <LoginPage isSignup={true} onPageChange={setCurrentPage} />}
        {currentPage === 'dashboard' && <DashboardPage onPageChange={setCurrentPage} />}
        {currentPage === 'replay' && <ReplayPage />}
        {currentPage === 'research' && <ResearchPage />}
      </main>
    </div>
  );
}

export default App;
