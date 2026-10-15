import { useState } from 'react';
import {
  BookOpen, CheckCircle2,
  TrendingUp, TrendingDown, Minus, Award, RotateCcw,
  PlayCircle, Circle, X, ArrowLeft
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctAnswer: number;
  explanation: string;
}

const quizData: Record<string, QuizQuestion[]> = {
  'candlestick-basics': [
    {
      id: 'q1',
      question: 'What does a green (bullish) candlestick indicate?',
      options: [
        'The closing price was lower than the opening price',
        'The closing price was higher than the opening price',
        'The price remained unchanged',
        'The market was closed'
      ],
      correctAnswer: 1,
      explanation: 'A green (bullish) candlestick indicates that the closing price was higher than the opening price, showing buying pressure.'
    },
    {
      id: 'q2',
      question: 'What are the four main components of a candlestick?',
      options: [
        'Open, High, Low, Close',
        'Buy, Sell, Hold, Wait',
        'Support, Resistance, Trend, Volume',
        'MACD, RSI, SMA, EMA'
      ],
      correctAnswer: 0,
      explanation: 'The four main components are Open (opening price), High (highest price), Low (lowest price), and Close (closing price).'
    }
  ],
  'hammer': [
    {
      id: 'q1',
      question: 'Where does the Hammer pattern typically appear?',
      options: [
        'At the top of an uptrend',
        'At the bottom of a downtrend',
        'In the middle of a trend',
        'Only in sideways markets'
      ],
      correctAnswer: 1,
      explanation: 'The Hammer pattern typically appears at the bottom of a downtrend and signals a potential bullish reversal.'
    },
    {
      id: 'q2',
      question: 'What is the key characteristic of a Hammer candlestick?',
      options: [
        'Long upper wick and small body',
        'Long lower wick and small body at the top',
        'No wicks and large body',
        'Equal upper and lower wicks'
      ],
      correctAnswer: 1,
      explanation: 'A Hammer has a long lower wick (about 2-3 times the body) and a small body at the top of the range.'
    }
  ],
  'shooting-star': [
    {
      id: 'q1',
      question: 'What does a Shooting Star pattern indicate?',
      options: [
        'Bullish continuation',
        'Bearish reversal',
        'Market consolidation',
        'High volatility'
      ],
      correctAnswer: 1,
      explanation: 'A Shooting Star is a bearish reversal pattern that appears at the top of an uptrend.'
    }
  ],
  'doji': [
    {
      id: 'q1',
      question: 'What does a Doji candlestick represent?',
      options: [
        'Strong buying pressure',
        'Strong selling pressure',
        'Market indecision',
        'Trend continuation'
      ],
      correctAnswer: 2,
      explanation: 'A Doji represents market indecision, where buying and selling pressures are in equilibrium.'
    }
  ]
};

const lessonCategories = [
  {
    id: 'basics',
    title: 'Basics',
    icon: BookOpen,
    lessons: [
      { id: 'intro-daytrading', title: 'Introduction to Day Trading' },
      { id: 'technical-analysis', title: 'What is Technical Analysis?' },
      { id: 'risk-basics', title: 'Risk Management Basics' },
    ]
  },
  {
    id: 'candlestick-patterns',
    title: 'Candlestick Patterns',
    icon: TrendingUp,
    lessons: [
      { id: 'candlestick-basics', title: 'What Are Candlesticks?' },
      { id: 'hammer', title: 'Bullish: Hammer' },
      { id: 'morning-star', title: 'Bullish: Morning Star' },
      { id: 'bullish-engulfing', title: 'Bullish: Engulfing' },
      { id: 'shooting-star', title: 'Bearish: Shooting Star' },
      { id: 'evening-star', title: 'Bearish: Evening Star' },
      { id: 'bearish-engulfing', title: 'Bearish: Engulfing' },
      { id: 'doji', title: 'Bilateral: Doji' },
      { id: 'spinning-top', title: 'Bilateral: Spinning Top' },
    ]
  },
  {
    id: 'chart-patterns',
    title: 'Chart Patterns',
    icon: TrendingDown,
    lessons: [
      { id: 'support-resistance', title: 'Support and Resistance' },
      { id: 'double-patterns', title: 'Double Top/Bottom' },
      { id: 'head-shoulders', title: 'Head and Shoulders' },
      { id: 'triangles', title: 'Triangles' },
    ]
  },
  {
    id: 'indicators',
    title: 'Technical Indicators',
    icon: Minus,
    lessons: [
      { id: 'moving-averages', title: 'Moving Averages' },
      { id: 'macd', title: 'MACD' },
      { id: 'rsi', title: 'RSI' },
    ]
  },
  {
    id: 'risk-management',
    title: 'Risk Management',
    icon: Award,
    lessons: [
      { id: 'position-sizing', title: 'Position Sizing' },
      { id: 'stop-loss', title: 'Stop Loss Strategies' },
    ]
  },
];

export function LearnerPage() {
  const [activeLesson, setActiveLesson] = useState('intro-daytrading');
  const [completedLessons, setCompletedLessons] = useState<string[]>([]);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number | null>>({});
  const [showQuizResults, setShowQuizResults] = useState<Record<string, boolean>>({});
  const [mobileLesson, setMobileLesson] = useState<string | null>(null);

  const handleQuizAnswer = (lessonId: string, questionId: string, answerIndex: number) => {
    setQuizAnswers(prev => ({ ...prev, [`${lessonId}-${questionId}`]: answerIndex }));
  };

  const checkQuizAnswer = (lessonId: string, questionId: string, correctAnswer: number) => {
    const userAnswer = quizAnswers[`${lessonId}-${questionId}`];
    return userAnswer === correctAnswer;
  };

  const markLessonComplete = (lessonId: string) => {
    if (!completedLessons.includes(lessonId)) {
      setCompletedLessons(prev => [...prev, lessonId]);
    }
    // On mobile, close the overlay and return to the lesson list
    setMobileLesson(null);
  };

  const calculateProgress = () => {
    const totalLessons = 20; // Approx total
    return Math.round((completedLessons.length / totalLessons) * 100);
  };

  const renderQuiz = (lessonId: string) => {
    if (!quizData[lessonId]) return null;
    return (
      <div className="mt-12 bg-white/[0.02] rounded-3xl p-8 border border-white/5">
        <h3 className="text-2xl font-black mb-8 flex items-center gap-3">
          <Award className="w-6 h-6 text-[#22c55e]" />
          Knowledge Check
        </h3>
        <div className="space-y-8">
          {quizData[lessonId].map((q, idx) => (
            <div key={q.id}>
              <p className="font-bold text-lg mb-4 text-white/90">{idx + 1}. {q.question}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {q.options.map((option, optIdx) => {
                  const answerKey = `${lessonId}-${q.id}`;
                  const isSelected = quizAnswers[answerKey] === optIdx;
                  const isCorrect = optIdx === q.correctAnswer;
                  const showResult = showQuizResults[answerKey];

                  return (
                    <button
                      key={optIdx}
                      onClick={() => !showResult && handleQuizAnswer(lessonId, q.id, optIdx)}
                      disabled={showResult}
                      className={`w-full text-left p-4 rounded-2xl border transition-all duration-300 font-medium ${showResult
                        ? isCorrect
                          ? 'bg-[#22c55e]/10 border-[#22c55e]/50 text-[#22c55e]'
                          : isSelected
                            ? 'bg-red-500/10 border-red-500/50 text-red-500'
                            : 'bg-white/[0.01] border-white/5 text-white/30'
                        : isSelected
                          ? 'bg-white/[0.05] border-white/30 text-white'
                          : 'bg-white/[0.01] border-white/5 text-white/60 hover:bg-white/[0.03] hover:border-white/20'
                        }`}
                    >
                      <div className="flex items-center justify-between">
                        <span>{option}</span>
                        {showResult && isCorrect && <CheckCircle2 className="w-5 h-5" />}
                        {showResult && !isCorrect && isSelected && <CheckCircle2 className="w-5 h-5 opacity-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>

              {!showQuizResults[`${lessonId}-${q.id}`] ? (
                <button
                  onClick={() => setShowQuizResults(prev => ({ ...prev, [`${lessonId}-${q.id}`]: true }))}
                  disabled={quizAnswers[`${lessonId}-${q.id}`] === undefined}
                  className="mt-4 bg-white/10 hover:bg-white/20 text-white disabled:opacity-30 disabled:hover:bg-white/10 px-6 py-2.5 rounded-xl font-bold transition-all text-sm uppercase tracking-widest"
                >
                  Verify Answer
                </button>
              ) : (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`mt-4 p-5 rounded-2xl ${checkQuizAnswer(lessonId, q.id, q.correctAnswer) ? 'bg-[#22c55e]/5 border border-[#22c55e]/10' : 'bg-red-500/5 border border-red-500/10'}`}>
                  <p className={`font-black uppercase tracking-widest text-xs mb-2 ${checkQuizAnswer(lessonId, q.id, q.correctAnswer) ? 'text-[#22c55e]' : 'text-red-500'}`}>
                    {checkQuizAnswer(lessonId, q.id, q.correctAnswer) ? 'Correct ✓' : 'Incorrect ✗'}
                  </p>
                  <p className="text-white/60 text-sm leading-relaxed font-light">{q.explanation}</p>
                  {!checkQuizAnswer(lessonId, q.id, q.correctAnswer) && (
                    <button
                      onClick={() => {
                        setShowQuizResults(prev => ({ ...prev, [`${lessonId}-${q.id}`]: false }));
                        setQuizAnswers(prev => ({ ...prev, [`${lessonId}-${q.id}`]: null }));
                      }}
                      className="mt-4 flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-white/40 hover:text-white transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" /> Retry Question
                    </button>
                  )}
                </motion.div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderLessonContent = () => {
    let content;
    switch (activeLesson) {
      case 'intro-daytrading':
        content = (
          <div className="space-y-6">
            <span className="text-[10px] font-black uppercase tracking-widest text-white/40 bg-white/5 px-2.5 py-1 rounded-sm">Module: Basics</span>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-8">Introduction to Day Trading</h2>
            <div className="prose prose-invert max-w-none prose-lg font-light text-white/60">
              <p className="text-xl text-white/80 leading-relaxed max-w-3xl mb-10">
                Day trading is the practice of buying and selling financial instruments within the same trading day. Unlike long-term investing, day traders aim to profit from short-term price movements derived from structural inefficiencies.
              </p>
              <h3 className="text-2xl font-bold tracking-tight text-white mt-12 mb-6">What You Will Master</h3>
              <div className="grid sm:grid-cols-2 gap-4 not-prose">
                {[
                  'Identify institutional footprints via volume patterns',
                  'Spot key reversal and continuation market structures',
                  'Confluence trading using advanced indicators',
                  'Capital preservation and robust risk management'
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-4 p-5 rounded-2xl bg-white/[0.02] border border-white/5">
                    <CheckCircle2 className="w-5 h-5 text-[#22c55e] shrink-0 mt-0.5" />
                    <span className="text-white/70 font-medium">{item}</span>
                  </div>
                ))}
              </div>
              <h3 className="text-2xl font-bold tracking-tight text-white mt-12 mb-6">The Edge</h3>
              <p className="leading-relaxed">
                True day trading eliminates overnight risk. You close your workstation completely flat (in cash). However, to be profitable, it requires extreme discipline, systematic edge, and a robotic execution mindset. This platform is designed to build exactly that framework for you.
              </p>
            </div>
          </div>
        );
        break;
      case 'candlestick-basics':
        content = (
          <div className="space-y-6">
            <span className="text-[10px] font-black uppercase tracking-widest text-[#22c55e]/60 bg-[#22c55e]/10 px-2.5 py-1 rounded-sm">Module: Patterns</span>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-8">Anatomy of a Candlestick</h2>
            <p className="text-xl font-light text-white/80 leading-relaxed max-w-3xl mb-12">
              A candlestick mathematically maps price action over a specific timeframe, instantly distilling market psychology, volatility, and order flow momentum into a single visual block.
            </p>
            <div className="grid md:grid-cols-2 gap-8 items-center mb-12">
              <div className="space-y-4">
                <h3 className="text-2xl font-bold tracking-tight mb-6">Structural Elements</h3>
                <div className="space-y-3">
                  <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                    <span className="font-bold text-white mr-2">Real Body:</span>
                    <span className="text-white/60 font-light">The absolute distance between the Open and Close. Shows pure price discovery.</span>
                  </div>
                  <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
                    <span className="font-bold text-white mr-2">Wicks / Tails:</span>
                    <span className="text-white/60 font-light">The highest and lowest price points touched. Measures intraday rejection and liquidity grabs.</span>
                  </div>
                </div>
              </div>
              <div className="bg-[#0a0a0a] rounded-3xl p-8 border border-white/5 flex justify-evenly items-center shadow-2xl">
                <div className="flex flex-col items-center">
                  <div className="w-16 h-40 bg-[#22c55e] bg-gradient-to-t from-[#22c55e]/80 to-[#22c55e] rounded-sm relative shadow-[0_0_30px_rgba(34,197,94,0.3)]">
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 w-1.5 h-8 bg-[#22c55e]" />
                    <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 w-1.5 h-6 bg-[#22c55e]" />
                  </div>
                  <span className="mt-10 font-black tracking-widest uppercase text-xs text-[#22c55e]">Bullish</span>
                </div>
                <div className="flex flex-col items-center">
                  <div className="w-16 h-32 bg-red-500 bg-gradient-to-t from-red-500/80 to-red-500 rounded-sm relative shadow-[0_0_30px_rgba(239,68,68,0.2)]">
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 w-1.5 h-6 bg-red-500" />
                    <div className="absolute -bottom-10 left-1/2 -translate-x-1/2 w-1.5 h-10 bg-red-500" />
                  </div>
                  <span className="mt-10 font-black tracking-widest uppercase text-xs text-red-500">Bearish</span>
                </div>
              </div>
            </div>
          </div>
        );
        break;
      default:
        content = (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <BookOpen className="w-16 h-16 text-white/10 mb-6" />
            <h2 className="text-3xl font-black text-white/40 mb-2">Lesson Under Construction</h2>
            <p className="text-white/20 font-light">We are meticulously crafting the high-fidelity data for this module.</p>
          </div>
        );
    }

    return (
      <AnimatePresence mode="wait">
        <motion.div
          key={activeLesson}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
        >
          {content}
          {renderQuiz(activeLesson)}
          <div className="mt-12 pt-8 border-t border-white/5 flex flex-col sm:flex-row items-center justify-between gap-4">
            <button
              onClick={() => markLessonComplete(activeLesson)}
              className="w-full sm:w-auto px-8 py-4 rounded-xl font-bold flex items-center justify-center gap-2 bg-[#22c55e] text-black hover:bg-[#1eb053] transition-colors"
            >
              <CheckCircle2 className="w-5 h-5" /> Execute & Complete Lesson
            </button>
          </div>
        </motion.div>
      </AnimatePresence>
    );
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-[#22c55e]/30">
      {/* Background elements */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-1/4 w-[50vw] h-[50vw] bg-white/[0.015] blur-[150px] rounded-full mix-blend-screen" />
        <div className="absolute bottom-0 left-1/4 w-[40vw] h-[40vw] bg-white/[0.01] blur-[100px] rounded-full mix-blend-screen" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.15] mix-blend-overlay pointer-events-none" />
      </div>

      {/* Top header */}
      <div className="relative z-20 border-b border-white/5 bg-[#050505]/80 backdrop-blur-xl">
        <div className="max-w-[1400px] mx-auto px-6 py-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
            <div>
              <h1 className="text-3xl font-black uppercase tracking-tight mb-2">The Trading Academy</h1>
              <p className="text-white/40 text-sm font-light uppercase tracking-widest max-w-xl leading-relaxed">Systematic curriculum designed to transition you from retail speculation to institutional execution.</p>
            </div>
            <div className="flex items-center gap-4 bg-white/[0.02] border border-white/5 rounded-2xl p-4 min-w-[300px]">
              <div className="relative w-12 h-12 flex items-center justify-center bg-[#22c55e]/10 rounded-xl">
                <Award className="w-6 h-6 text-[#22c55e]" />
              </div>
              <div className="flex-1">
                <div className="flex justify-between text-[10px] uppercase font-bold tracking-widest mb-2 text-white/50">
                  <span>Progress</span>
                  <span className="text-[#22c55e]">{calculateProgress()}%</span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${calculateProgress()}%` }}
                    transition={{ duration: 1, ease: 'easeOut' }}
                    className="h-full bg-gradient-to-r from-[#22c55e]/50 to-[#22c55e] rounded-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="relative z-10 max-w-[1400px] mx-auto px-6 py-12">
        <div className="grid lg:grid-cols-12 gap-12">

          {/* Sidebar / Syllabus */}
          <div className="lg:col-span-3 space-y-6">
            <div className="text-xs font-black uppercase tracking-widest text-white/30 px-2">Knowledge Base</div>
            {lessonCategories.map((category) => (
              <div key={category.id} className="bg-white/[0.01] rounded-2xl border border-white/5 overflow-hidden">
                <div className="p-4 flex items-center gap-3 border-b border-white/5 bg-white/[0.02]">
                  <category.icon className="w-4 h-4 text-white/50" />
                  <h3 className="font-bold text-sm tracking-wide text-white/80">{category.title}</h3>
                </div>
                <div className="p-2 space-y-1">
                  {category.lessons.map((lesson) => {
                    const isCompleted = completedLessons.includes(lesson.id);
                    const isActive = activeLesson === lesson.id;
                    return (
                      <button
                        key={lesson.id}
                        onClick={() => {
                          setActiveLesson(lesson.id);
                          // On mobile, open the full-page overlay
                          if (window.innerWidth < 1024) setMobileLesson(lesson.id);
                        }}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm transition-all
                                                    ${isActive
                            ? 'bg-white/10 text-white shadow-sm'
                            : 'text-white/40 hover:bg-white/5 hover:text-white/80'}`}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#22c55e]' : 'text-white/20'}`} />
                        ) : isActive ? (
                          <PlayCircle className="w-4 h-4 shrink-0 text-[#22c55e]" />
                        ) : (
                          <Circle className="w-4 h-4 shrink-0 opacity-20" />
                        )}
                        <span className={`${isActive ? 'font-semibold' : 'font-light truncate'}`}>
                          {lesson.title}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Reader Pane (Desktop only) */}
          <div className="hidden lg:block lg:col-span-9">
            <div className="bg-[#0a0a0a] border border-white/5 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden">
              {/* Inner subtle glow */}
              <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-white/[0.02] blur-[150px] rounded-full pointer-events-none" />
              <div className="relative z-10">
                {renderLessonContent()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Mobile full-page lesson view ── */}
      {mobileLesson && (
        <div className="lg:hidden fixed inset-0 z-[100] bg-[#050505] flex flex-col">
          {/* Fixed top bar */}
          <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#050505]">
            <button
              onClick={() => setMobileLesson(null)}
              className="flex items-center gap-2 text-white/70 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
              <span className="text-sm font-bold uppercase tracking-wide">Back</span>
            </button>
            <button
              onClick={() => setMobileLesson(null)}
              className="p-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/70 hover:text-white transition-all active:scale-90"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scrollable lesson content */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-5 sm:p-8">
              <div className="relative z-10">
                {renderLessonContent()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
