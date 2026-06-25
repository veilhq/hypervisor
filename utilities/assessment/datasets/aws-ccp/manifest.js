// ===================================================================
// AWS CCP (CLF-C02) — Quiz Manifest
// ===================================================================
// Configuration for the generic assessment engine.
// This file defines the quiz identity, domains, scoring, and display
// settings. The engine reads this to adapt its behavior.
// ===================================================================

window.QUIZ_MANIFEST = {
  id: "aws-ccp",
  title: "AWS CCP Practice Quiz",
  icon: "cloud",

  // CLF-C02 exam domains
  domains: {
    1: "Cloud Concepts",
    2: "Security & Compliance",
    3: "Technology & Services",
    4: "Billing & Support"
  },

  // Official CLF-C02 domain weights
  weights: {
    1: 0.24,
    2: 0.30,
    3: 0.34,
    4: 0.12
  },

  // Scoring — 700/1000 scaled score ≈ 72-75% correct
  passThreshold: 72,
  passLabel: "PASS (700+)",
  failLabel: "NEEDS WORK (<700)",
  scoreNote: "Real exam: 700/1000 scaled score (~72-75% correct)",

  // Question metadata
  questionTypes: ["recall", "scenario"],

  // Exam structure
  fullExamCount: 65,
  questionCounts: [10, 20, 35, 50]
};
