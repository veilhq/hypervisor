// ===================================================================
// Assessment Dataset Registry
// ===================================================================
// Lists all available datasets. The engine reads this to build the
// dataset selector and load the correct files.
//
// Each entry:
//   id    — unique slug (matches the subdirectory name under datasets/)
//   title — display name shown in the selector and page title
//   icon  — lucide icon name (optional, for future use)
//   files — array of JS filenames to load from datasets/{id}/
//           (loaded in order: manifest first, then questions, then guide)
//
// To add a new dataset:
//   1. Create datasets/{id}/ with manifest.js, questions.js, study-guide.js
//   2. Add an entry here
//   3. Rebuild
// ===================================================================

window.QUIZ_DATASETS = [
  {
    id: "aws-ccp",
    title: "AWS Cloud Practitioner (CLF-C02)",
    icon: "cloud",
    files: ["manifest.js", "questions.js", "study-guide.js"]
  }
];
