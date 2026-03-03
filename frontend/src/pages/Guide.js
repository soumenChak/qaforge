import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  QuestionMarkCircleIcon,
  MagnifyingGlassIcon,
  ChevronDownIcon,
  RocketLaunchIcon,
  BeakerIcon,
  PlayIcon,
  BookOpenIcon,
  ShieldCheckIcon,
  CommandLineIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  ArrowTopRightOnSquareIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';

/* ───────────────────────────── constants ───────────────────────────── */

const ROLE_BADGE = {
  everyone: 'bg-fg-teal/15 text-fg-teal',
  admin: 'bg-red-100 text-red-700',
  engineer: 'bg-blue-100 text-blue-700',
};

const CATEGORY_META = {
  'getting-started': { label: 'Getting Started', icon: RocketLaunchIcon, accent: 'from-fg-teal to-fg-green' },
  'test-cases':      { label: 'Test Case Workflows', icon: BeakerIcon, accent: 'from-blue-400 to-indigo-500' },
  'execution':       { label: 'Test Execution', icon: PlayIcon, accent: 'from-green-400 to-emerald-500' },
  'knowledge':       { label: 'Knowledge Base', icon: BookOpenIcon, accent: 'from-purple-400 to-violet-500' },
  'admin':           { label: 'Admin Workflows', icon: ShieldCheckIcon, accent: 'from-amber-400 to-orange-500' },
  'cli':             { label: 'qaforge.py CLI Reference', icon: CommandLineIcon, accent: 'from-gray-500 to-gray-700' },
};

/* ───────────────────────────── guide data ──────────────────────────── */

const GUIDE_SCENARIOS = [
  /* ── Getting Started ────────────────────────────────────────────── */
  {
    id: 'first-login',
    title: 'First Login & Setup',
    role: 'everyone',
    category: 'getting-started',
    description: 'Log in, change your password, and navigate the platform.',
    prerequisites: ['A QAForge account (admin creates it for you)', 'Browser access to the QAForge URL'],
    steps: [
      'Navigate to your QAForge URL (e.g. https://your-server:8080) and enter your email and password.',
      'After login you land on the **Dashboard** — this shows pending reviews, active projects, and pass rates.',
      'Use the **sidebar** to navigate: Projects, Review Queue, Knowledge Base, and (for admins) Settings & Users.',
      'Go to **Users** (or ask your admin) and click **Change Password** to set a strong password.',
      'Explore the Dashboard to see pending review counts and your assigned projects.',
    ],
    tips: ['Bookmark the QAForge URL for quick access.', 'Your JWT token expires after 24 hours — you will be redirected to login automatically.'],
    warnings: ['Change the default password immediately after first login.'],
  },
  {
    id: 'create-project',
    title: 'Create Your First Project',
    role: 'admin',
    category: 'getting-started',
    description: 'Use the Project Wizard to create a project, assign engineers, and generate an agent key.',
    prerequisites: ['Admin role', 'At least one engineer user created'],
    steps: [
      'Go to **Projects** from the sidebar and click **New Project**.',
      '**Step 1 — Details:** Enter a project name, select the domain (MDM, AI, Data Engineering, etc.), optionally add a sub-domain and description. Check "Auto-generate Agent Key" if agents will submit test results.',
      '**Step 2 — Team:** Select engineers to assign. They will only see this project in their dashboard.',
      '**Step 3 — Success:** Copy the generated agent key and the setup instructions. Share these with your engineer.',
      'The project now appears on the Projects page. Click into it to add requirements, generate test cases, and create test plans.',
    ],
    tips: ['The agent key is shown only once — copy it immediately.', 'You can regenerate a key later from the project detail page.'],
    cli: null,
    related: ['connect-agent', 'generate-from-requirements'],
  },
  {
    id: 'connect-agent',
    title: 'Connect Your Agent (qaforge.py)',
    role: 'engineer',
    category: 'getting-started',
    description: 'Set up the qaforge.py CLI to connect your development environment to QAForge.',
    prerequisites: ['Python 3.8+', 'Agent key or bootstrap token from admin', 'qaforge.py script in your project\'s scripts/ folder'],
    steps: [
      'Get the agent key from your admin (or the bootstrap token if self-onboarding).',
      'Run the setup command — this saves the API URL and key to your `.env` file:',
      'Verify connectivity:',
      'You are now ready to submit test cases, run tests, and sync results with QAForge.',
    ],
    cli: [
      { label: 'Option A: Setup with agent key', cmd: 'python scripts/qaforge.py setup \\\n  --project "My Project" \\\n  --token "qf_your_agent_key_here"' },
      { label: 'Option B: Bootstrap (self-onboarding)', cmd: 'python scripts/qaforge.py setup \\\n  --project "My Project" \\\n  --token "bootstrap-token-from-admin" \\\n  --domain mdm --sub-domain reltio' },
      { label: 'Verify', cmd: 'python scripts/qaforge.py status' },
    ],
    tips: ['The setup command creates/updates QAFORGE_API_URL and QAFORGE_AGENT_KEY in your .env file.', 'qaforge.py auto-installs the openpyxl dependency if needed.'],
    related: ['create-project'],
  },

  /* ── Test Case Workflows ────────────────────────────────────────── */
  {
    id: 'generate-from-requirements',
    title: 'Generate Test Cases from Requirements',
    role: 'everyone',
    category: 'test-cases',
    description: 'Add requirements to a project, then use AI to auto-generate test cases.',
    prerequisites: ['An active project', 'At least one requirement added'],
    steps: [
      'Open your project and go to the **Requirements** tab.',
      'Click **Add Requirement** — enter a title, description, priority (high/medium/low), and source (BRD/PRD/manual).',
      'Alternatively, paste raw BRD/PRD text and click **Extract** to let AI parse it into structured requirements.',
      'Go to the **Test Cases** tab and click **Generate**.',
      'Select which requirements to generate from, choose priority and category, then click **Generate Test Cases**.',
      'AI generates test cases with steps, expected results, priority, and category. They appear with "draft" status.',
      'Review them in the **Review Queue** — approve, reject, or request changes.',
    ],
    tips: ['Add as many requirements as possible before generating — the AI uses all of them for context.', 'Higher priority requirements get more thorough test cases.'],
    related: ['review-results', 'generate-from-brd'],
  },
  {
    id: 'generate-from-brd',
    title: 'Generate Enterprise Test Cases from BRD (Excel)',
    role: 'engineer',
    category: 'test-cases',
    description: 'Use qaforge.py to generate domain-specific test cases from a BRD spreadsheet with reference examples.',
    prerequisites: ['qaforge.py connected (run setup first)', 'BRD Excel file (.xlsx)', 'Optional: Reference test case Excel for in-context learning'],
    steps: [
      'Prepare your BRD Excel file — it should contain requirement descriptions, acceptance criteria, or specifications.',
      'Optionally prepare a reference Excel with example test cases — QAForge learns the format and style from these.',
      'Run the generate command (see CLI below).',
      'QAForge reads the BRD, retrieves relevant KB patterns, uses the reference for style, and generates domain-specific test cases.',
      'Generated test cases appear in your project with "draft" status — review them in the Review Queue.',
    ],
    cli: [
      { label: 'With reference (recommended)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/Sample_MDM_TC.xlsx \\\n  --reference ~/Desktop/Sample_MDM_TC.xlsx \\\n  --domain mdm --sub-domain reltio --count 10' },
      { label: 'Without reference (uses KB)', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/new_requirement.xlsx \\\n  --domain mdm --sub-domain reltio --count 5' },
      { label: 'Data Engineering domain', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd ~/Desktop/DE_Specs.xlsx \\\n  --reference ~/Desktop/Sample_DE_TC.xlsx \\\n  --domain data_eng --sub-domain snowflake --count 10' },
    ],
    tips: [
      'The first time you provide a reference Excel, QAForge auto-saves it to the Knowledge Base for future use.',
      'On subsequent runs without --reference, QAForge auto-retrieves the best matching reference from KB.',
      'Supported domains: mdm, ai, data_eng, integration, digital, app.',
    ],
    warnings: ['Large BRD files may take 30-60 seconds to process depending on your LLM provider.'],
    related: ['upload-reference', 'connect-agent'],
  },
  {
    id: 'chat-generate',
    title: 'Chat-Based Test Generation',
    role: 'everyone',
    category: 'test-cases',
    description: 'Have an interactive conversation with AI to generate test cases through back-and-forth dialog.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Chat Generate** (or use the chat icon).',
      'Describe what you want to test in natural language — e.g., "I need test cases for the customer entity load from Snowflake to Reltio."',
      'The AI may ask clarifying questions about edge cases, data volumes, or specific scenarios.',
      'Continue the dialog until the AI generates test cases you are satisfied with.',
      'Click **Save** to add the generated test cases to your project with "draft" status.',
    ],
    tips: ['Be specific about your domain — mention technologies, table names, and business rules.', 'You can refine test cases in the conversation: "Make TC-3 more detailed" or "Add a negative test case."'],
    related: ['generate-from-requirements'],
  },
  {
    id: 'bulk-upload',
    title: 'Bulk Upload Test Cases from Excel',
    role: 'everyone',
    category: 'test-cases',
    description: 'Download a template, fill it with test cases, and upload in bulk.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Upload** and then **Download Template** to get the Excel template.',
      'Fill in the template columns: test_case_id, title, description, steps, expected_result, priority (P1-P4), category, execution_type.',
      'Save the Excel file and click **Upload** → select your filled template.',
      'QAForge validates and imports all test cases. Invalid rows are reported with error details.',
      'Uploaded test cases appear with "draft" status for review.',
    ],
    tips: ['Keep test_case_id unique (e.g., TC-AUTH-001, TC-MDM-001).', 'You can upload hundreds of test cases at once.'],
    related: ['export-test-cases'],
  },
  {
    id: 'manual-test-case',
    title: 'Create Test Cases Manually',
    role: 'everyone',
    category: 'test-cases',
    description: 'Add individual test cases through the web form.',
    prerequisites: ['An active project'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Add Test Case**.',
      'Fill in: title, description, steps (numbered), expected result, priority (P1-P4), category (functional, integration, etc.), and execution type (api, ui, sql, manual, mdm).',
      'Click **Save**. The test case is created with "draft" status.',
      'You can edit it anytime by clicking the test case row.',
    ],
    tips: ['Use clear, action-oriented titles: "Verify customer entity load count matches source."'],
    related: ['bulk-upload'],
  },
  {
    id: 'export-test-cases',
    title: 'Export Test Cases',
    role: 'everyone',
    category: 'test-cases',
    description: 'Download test cases as Excel, Word, JSON, or CSV.',
    prerequisites: ['A project with test cases'],
    steps: [
      'Open your project and go to the **Test Cases** tab.',
      'Click **Export**.',
      'Choose the format: Excel (.xlsx), Word (.docx), JSON, or CSV.',
      'Optionally filter by status, priority, or category before exporting.',
      'Click **Download** — the file is generated and downloaded to your browser.',
    ],
    tips: ['Excel export includes all metadata: steps, expected results, actual results, and proof references.'],
  },

  /* ── Test Execution Workflows ───────────────────────────────────── */
  {
    id: 'create-test-plan',
    title: 'Create a Test Plan',
    role: 'everyone',
    category: 'execution',
    description: 'Organize test cases into SIT, UAT, Regression, or custom test plans.',
    prerequisites: ['A project with test cases'],
    steps: [
      'Open your project and click **Test Plans** in the sidebar or project tabs.',
      'Click **Create Test Plan**.',
      'Enter a name, select the plan type (SIT, UAT, Regression, Smoke, Migration, Custom), and add a description.',
      'Assign test cases to the plan — select from the project\'s test case list.',
      'The test plan dashboard shows: total cases, pass/fail counts, and completion percentage.',
      'Click into the plan to view test cases, execution results, traceability matrix, and summary.',
    ],
    tips: ['Use SIT plans for integration testing, UAT for user acceptance, and Regression for ongoing quality.'],
    related: ['submit-execution', 'review-results'],
  },
  {
    id: 'submit-execution',
    title: 'Submit Execution Results via Agent',
    role: 'engineer',
    category: 'execution',
    description: 'Run tests locally and auto-submit results (with proof artifacts) to QAForge.',
    prerequisites: ['qaforge.py connected', 'Tests written and runnable locally'],
    steps: [
      'Run your tests using one of the qaforge.py runner commands (see CLI below).',
      'qaforge.py captures: pass/fail status, duration, stdout/stderr, and (for Playwright) screenshots.',
      'Results are auto-submitted to QAForge with proof artifacts attached.',
      'Check results in the Review Queue or the project\'s Test Plans → Executions tab.',
    ],
    cli: [
      { label: 'Smoke tests', cmd: 'python scripts/qaforge.py run-smoke' },
      { label: 'pytest', cmd: 'python scripts/qaforge.py run-pytest backend/tests/' },
      { label: 'Playwright E2E', cmd: 'python scripts/qaforge.py run-playwright' },
      { label: 'Specific Playwright spec', cmd: 'python scripts/qaforge.py run-playwright --spec e2e/candidates.spec.js' },
    ],
    tips: [
      'Each run creates an "agent session" visible in the project dashboard.',
      'Proof artifacts include: api_response, test_output, screenshot, log, query_result, data_comparison.',
    ],
    related: ['review-results', 'connect-agent'],
  },
  {
    id: 'review-results',
    title: 'Review Test Results in the Review Queue',
    role: 'everyone',
    category: 'execution',
    description: 'Approve or reject test cases and execution results from a centralized review page.',
    prerequisites: ['Pending items in the Review Queue (generated test cases or submitted execution results)'],
    steps: [
      'Go to **Review Queue** from the sidebar.',
      '**Test Cases tab:** Shows all test cases with "draft" status across your projects. Click a row to expand and see the full test case details.',
      '**Executions tab:** Shows execution results awaiting review. Expand to see actual results, duration, and proof artifacts.',
      'Select items individually (checkboxes) or use **Select All**.',
      'Click **Approve Selected** to mark as reviewed/approved, or **Reject Selected** to deprecate.',
      'For executions, use **Approve All Passed** to auto-approve all items with a "passed" status.',
    ],
    tips: [
      'The Dashboard shows your total pending review count — use it as a daily starting point.',
      'Bulk operations save significant time when reviewing agent-generated test cases.',
    ],
    related: ['submit-execution', 'generate-from-requirements'],
  },

  /* ── Knowledge Base Workflows ───────────────────────────────────── */
  {
    id: 'seed-kb',
    title: 'Seed the Knowledge Base',
    role: 'admin',
    category: 'knowledge',
    description: 'Populate KB with reference patterns, anti-patterns, and best practices with one click.',
    prerequisites: ['Admin role'],
    steps: [
      'Go to **Knowledge Base** from the sidebar.',
      'Click **Seed Reference Data** button in the top-right.',
      'QAForge loads 30+ entries: API testing checklists, UI testing patterns, security testing patterns, CRUD lifecycle, login flows, search/filter patterns, and framework-specific anti-patterns.',
      'Entries are tagged by domain and type. They are used by the AI when generating test cases.',
      'Seeding is idempotent — running it again won\'t create duplicates.',
    ],
    tips: ['Seed the KB before generating any test cases — it significantly improves AI output quality.'],
    related: ['upload-reference', 'browse-kb'],
  },
  {
    id: 'upload-reference',
    title: 'Upload Reference Test Cases to KB',
    role: 'engineer',
    category: 'knowledge',
    description: 'Add domain-specific reference test cases from Excel so the AI learns your team\'s testing style.',
    prerequisites: ['qaforge.py connected', 'Reference Excel file with example test cases'],
    steps: [
      'Prepare an Excel file with reference test cases — these teach the AI your team\'s format, depth, and domain terminology.',
      'Run the upload command:',
      'QAForge parses the Excel, extracts test case patterns, and stores them in the Knowledge Base.',
      'Future test case generation will use these references for in-context learning.',
      'Verify with:',
    ],
    cli: [
      { label: 'Upload reference', cmd: 'python scripts/qaforge.py upload-reference \\\n  --file ~/Desktop/Sample_MDM_TC.xlsx \\\n  --domain mdm --sub-domain reltio' },
      { label: 'Check KB stats', cmd: 'python scripts/qaforge.py kb-stats --domain mdm' },
    ],
    tips: ['Upload references for each domain separately — MDM, Data Engineering, AI, etc.', 'The more examples you provide, the better the AI generates.'],
    related: ['seed-kb', 'generate-from-brd'],
  },
  {
    id: 'browse-kb',
    title: 'Browse & Search the Knowledge Base',
    role: 'everyone',
    category: 'knowledge',
    description: 'Find testing patterns, anti-patterns, and compliance rules across all domains.',
    prerequisites: [],
    steps: [
      'Go to **Knowledge Base** from the sidebar.',
      'Use the **Search** bar to find entries by keyword (e.g., "Reltio", "SQL injection", "CRUD").',
      'Filter by **domain** using the tabs: General, MDM, AI, Data Engineering, App.',
      'Each entry shows its type with a colored badge: pattern (teal), anti-pattern (orange), framework pattern (purple), compliance rule (indigo), etc.',
      'Entries with an "Auto-learned" badge were automatically saved from reference uploads.',
      'Click an entry to expand and see full content, tags, and usage count.',
    ],
    tips: ['Entries with high usage counts are frequently referenced by the AI — they are the most impactful.', 'Add your own entries to teach the AI about your specific domain.'],
    related: ['add-kb-entry'],
  },
  {
    id: 'add-kb-entry',
    title: 'Add Custom Knowledge Entries',
    role: 'everyone',
    category: 'knowledge',
    description: 'Manually add domain expertise, testing patterns, or anti-patterns to the Knowledge Base.',
    prerequisites: [],
    steps: [
      'Go to **Knowledge Base** and click **Add Entry**.',
      'Fill in: title, content (the detailed knowledge), domain, entry type, sub-domain, and tags.',
      '**Entry types:** pattern, defect, best_practice, test_case, framework_pattern, anti_pattern, compliance_rule.',
      'Click **Save**. The entry is immediately available for AI to use during test case generation.',
    ],
    tips: [
      'Use "anti_pattern" for things to avoid: "NEVER use html.escape() — causes double encoding."',
      'Use "compliance_rule" for mandatory checks: "Every route must call audit_log() for mutations."',
      'Use "framework_pattern" for architectural standards: "All DB access through database_pg.py."',
    ],
    related: ['browse-kb'],
  },

  /* ── Admin Workflows ────────────────────────────────────────────── */
  {
    id: 'manage-users',
    title: 'Manage Users',
    role: 'admin',
    category: 'admin',
    description: 'Add engineers, change roles, and deactivate accounts.',
    prerequisites: ['Admin role'],
    steps: [
      'Go to **Users** from the sidebar (admin section).',
      'Click **Add Engineer** to create a new user — enter name, email, password, and select roles (admin or engineer).',
      'To edit a user, click the pencil icon — you can change their name and role badges.',
      'To deactivate a user, click the X icon (you cannot deactivate yourself).',
      'Share the login credentials with the new user and ask them to change their password on first login.',
    ],
    tips: ['Engineers can only see projects they are assigned to. Admins see all projects.'],
    related: ['create-project'],
  },
  {
    id: 'configure-llm',
    title: 'Configure LLM Settings',
    role: 'admin',
    category: 'admin',
    description: 'Switch between AI providers and models for test case generation.',
    prerequisites: ['Admin role', 'API key for at least one provider'],
    steps: [
      'Go to **Settings** from the sidebar (admin section).',
      'You will see the current LLM provider and model.',
      'Available providers: **Anthropic** (Claude Sonnet/Haiku), **OpenAI** (GPT-4o/GPT-4o-mini), **Groq** (Llama 3.3/Mixtral), **Ollama** (local models).',
      'Select your preferred provider and model, then click **Save**.',
      'API keys are set via environment variables on the server (ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY).',
    ],
    tips: ['Groq offers the fastest generation (Llama 3.3 70B). Claude Sonnet gives the highest quality for enterprise test cases.', 'Use "mock" provider for testing without spending API credits.'],
    warnings: ['Changing the provider affects all users and all projects immediately.'],
  },
  {
    id: 'monitor-health',
    title: 'Monitor Platform Health',
    role: 'admin',
    category: 'admin',
    description: 'Use the Dashboard to monitor pending reviews, project status, and test pass rates.',
    prerequisites: ['Admin role'],
    steps: [
      'The **Dashboard** is your home page — it shows 4 key metrics:',
      '**Pending Reviews** — how many test cases and executions need human review. Click "Go to Review Queue" to process them.',
      '**Active Projects** — count of projects in "active" status.',
      '**Pass Rate** — overall pass rate across all projects.',
      '**KB Entries** — total knowledge base entries driving AI quality.',
      'Below the stats, see **My Projects** table with per-project pass rates and test case counts.',
    ],
    tips: ['Check the Dashboard daily — pending reviews should not accumulate. A healthy queue has < 20 items.'],
    related: ['review-results'],
  },

  /* ── CLI Reference ──────────────────────────────────────────────── */
  {
    id: 'cli-reference',
    title: 'qaforge.py — Full Command Reference',
    role: 'engineer',
    category: 'cli',
    description: 'Complete reference for every qaforge.py CLI command with examples.',
    prerequisites: ['Python 3.8+', 'qaforge.py in your project\'s scripts/ folder'],
    steps: [
      '**setup** — Initialize connection to QAForge (saves API URL + key to .env)',
      '**status** — Check connectivity and project status',
      '**run-smoke** — Run smoke tests and auto-submit results',
      '**run-pytest** — Run pytest and auto-submit results',
      '**run-playwright** — Run Playwright E2E tests with screenshot capture',
      '**generate-from-brd** — Generate test cases from BRD Excel with reference learning',
      '**upload-reference** — Upload reference test cases to Knowledge Base',
      '**kb-stats** — Show Knowledge Base statistics for a domain',
      '**summary** — Show project progress summary',
      '**submit-cases** — Submit test cases via JSON (stdin)',
      '**submit-results** — Submit execution results via JSON (stdin)',
    ],
    cli: [
      { label: 'Setup', cmd: 'python scripts/qaforge.py setup --project "Name" --token "key"' },
      { label: 'Status', cmd: 'python scripts/qaforge.py status' },
      { label: 'Run smoke tests', cmd: 'python scripts/qaforge.py run-smoke' },
      { label: 'Run pytest', cmd: 'python scripts/qaforge.py run-pytest backend/tests/' },
      { label: 'Run Playwright', cmd: 'python scripts/qaforge.py run-playwright' },
      { label: 'Run specific spec', cmd: 'python scripts/qaforge.py run-playwright --spec e2e/login.spec.js' },
      { label: 'Generate from BRD', cmd: 'python scripts/qaforge.py generate-from-brd \\\n  --brd file.xlsx --reference ref.xlsx \\\n  --domain mdm --sub-domain reltio --count 10' },
      { label: 'Upload reference', cmd: 'python scripts/qaforge.py upload-reference \\\n  --file sample.xlsx --domain mdm --sub-domain reltio' },
      { label: 'KB stats', cmd: 'python scripts/qaforge.py kb-stats --domain mdm' },
      { label: 'Summary', cmd: 'python scripts/qaforge.py summary' },
    ],
    tips: [
      'All commands read QAFORGE_API_URL and QAFORGE_AGENT_KEY from .env automatically.',
      'qaforge.py auto-installs openpyxl if needed (no pip install required).',
      'Domains: mdm | ai | data_eng | integration | digital | app.',
      'Categories: functional | integration | regression | smoke | e2e | data_quality | match_rule | migration.',
      'Priorities: P1 | P2 | P3 | P4.',
    ],
    related: ['connect-agent', 'submit-execution', 'generate-from-brd'],
  },
];

/* ───────────────────────────── sub-components ─────────────────────── */

function CodeBlock({ cmd, label }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="mb-3">
      {label && <p className="text-xs font-medium text-fg-mid mb-1">{label}</p>}
      <div className="relative group">
        <pre className="bg-gray-900 text-green-400 text-xs font-mono p-3 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
          {cmd}
        </pre>
        <button
          onClick={handleCopy}
          className="absolute top-2 right-2 text-gray-500 hover:text-green-400 text-xs font-mono opacity-0 group-hover:opacity-100 transition-opacity"
        >
          {copied ? 'copied!' : 'copy'}
        </button>
      </div>
    </div>
  );
}

function Tip({ children }) {
  return (
    <div className="flex gap-2 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm text-blue-800 mb-2">
      <LightBulbIcon className="w-4 h-4 flex-shrink-0 mt-0.5 text-blue-500" />
      <span>{children}</span>
    </div>
  );
}

function Warning({ children }) {
  return (
    <div className="flex gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-sm text-amber-800 mb-2">
      <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-500" />
      <span>{children}</span>
    </div>
  );
}

function ScenarioCard({ scenario, isOpen, onToggle, onNavigate }) {
  const roleBadgeClass = ROLE_BADGE[scenario.role] || ROLE_BADGE.everyone;

  return (
    <div className="border border-gray-100 rounded-xl bg-white hover:shadow-sm transition-shadow overflow-hidden">
      {/* Collapsed header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-5 py-4 text-left"
      >
        <ChevronDownIcon
          className={`w-4 h-4 text-fg-mid flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-fg-dark">{scenario.title}</span>
            <span className={`badge text-xxs ${roleBadgeClass}`}>{scenario.role}</span>
          </div>
          {!isOpen && (
            <p className="text-xs text-fg-mid mt-0.5 truncate">{scenario.description}</p>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isOpen && (
        <div className="px-5 pb-5 animate-fade-in">
          <p className="text-sm text-fg-mid mb-4">{scenario.description}</p>

          {/* Prerequisites */}
          {scenario.prerequisites && scenario.prerequisites.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Prerequisites</h4>
              <ul className="space-y-1">
                {scenario.prerequisites.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-fg-mid">
                    <ChevronRightIcon className="w-3 h-3 mt-0.5 text-fg-teal flex-shrink-0" />
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Steps */}
          <div className="mb-4">
            <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Steps</h4>
            <ol className="space-y-2">
              {scenario.steps.map((step, i) => (
                <li key={i} className="flex items-start gap-3 text-sm text-fg-dark">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-fg-teal/15 text-fg-teal text-xs font-bold flex items-center justify-center mt-0.5">
                    {i + 1}
                  </span>
                  <span dangerouslySetInnerHTML={{ __html: step.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />
                </li>
              ))}
            </ol>
          </div>

          {/* CLI Commands */}
          {scenario.cli && scenario.cli.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">CLI Commands</h4>
              {scenario.cli.map((c, i) => (
                <CodeBlock key={i} cmd={c.cmd} label={c.label} />
              ))}
            </div>
          )}

          {/* Tips */}
          {scenario.tips && scenario.tips.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Tips</h4>
              {scenario.tips.map((t, i) => (
                <Tip key={i}>{t}</Tip>
              ))}
            </div>
          )}

          {/* Warnings */}
          {scenario.warnings && scenario.warnings.length > 0 && (
            <div className="mb-4">
              {scenario.warnings.map((w, i) => (
                <Warning key={i}>{w}</Warning>
              ))}
            </div>
          )}

          {/* Related */}
          {scenario.related && scenario.related.length > 0 && (
            <div className="pt-3 border-t border-gray-100">
              <h4 className="text-xs font-bold text-fg-navy uppercase tracking-wider mb-2">Related</h4>
              <div className="flex flex-wrap gap-2">
                {scenario.related.map((relId) => {
                  const rel = GUIDE_SCENARIOS.find((s) => s.id === relId);
                  if (!rel) return null;
                  return (
                    <button
                      key={relId}
                      onClick={() => onNavigate(relId)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-fg-teal hover:text-fg-tealDark"
                    >
                      <ArrowTopRightOnSquareIcon className="w-3 h-3" />
                      {rel.title}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ───────────────────────────── main page ──────────────────────────── */

export default function Guide() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [openIds, setOpenIds] = useState(new Set());
  const [allExpanded, setAllExpanded] = useState(false);

  const categories = Object.keys(CATEGORY_META);

  // Filter scenarios
  const filtered = useMemo(() => {
    return GUIDE_SCENARIOS.filter((s) => {
      if (roleFilter !== 'all' && s.role !== roleFilter && s.role !== 'everyone') return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          s.title.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          (s.steps && s.steps.some((st) => st.toLowerCase().includes(q))) ||
          (s.tips && s.tips.some((t) => t.toLowerCase().includes(q)))
        );
      }
      return true;
    });
  }, [search, roleFilter]);

  const toggle = (id) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const navigateToScenario = (id) => {
    setOpenIds((prev) => new Set(prev).add(id));
    setTimeout(() => {
      document.getElementById(`scenario-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  };

  const toggleAll = () => {
    if (allExpanded) {
      setOpenIds(new Set());
    } else {
      setOpenIds(new Set(filtered.map((s) => s.id)));
    }
    setAllExpanded(!allExpanded);
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div className="section-header">
        <div>
          <div className="flex items-center gap-2">
            <QuestionMarkCircleIcon className="w-7 h-7 text-fg-teal" />
            <h1 className="text-2xl font-bold text-fg-navy">Usage Guide</h1>
          </div>
          <p className="text-sm text-fg-mid mt-1">
            {filtered.length} scenario{filtered.length !== 1 ? 's' : ''} — step-by-step walkthroughs for every workflow
          </p>
        </div>
        <button onClick={toggleAll} className="btn-secondary text-sm">
          {allExpanded ? 'Collapse All' : 'Expand All'}
        </button>
      </div>

      {/* Search + Role Tabs */}
      <div className="card-static p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search guide... (e.g. BRD, Reltio, pytest, review)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field pl-9 text-sm"
            />
          </div>
          {/* Role filter */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {[
              { key: 'all', label: 'All' },
              { key: 'admin', label: 'Admin' },
              { key: 'engineer', label: 'Engineer' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setRoleFilter(tab.key)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  roleFilter === tab.key
                    ? 'bg-white text-fg-navy shadow-sm'
                    : 'text-fg-mid hover:text-fg-dark'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Categories + Scenarios */}
      <div className="space-y-8">
        {categories.map((catKey) => {
          const catMeta = CATEGORY_META[catKey];
          const catScenarios = filtered.filter((s) => s.category === catKey);
          if (catScenarios.length === 0) return null;

          const CatIcon = catMeta.icon;

          return (
            <div key={catKey}>
              {/* Category header */}
              <div className="card-static overflow-hidden">
                <div className={`h-1 bg-gradient-to-r ${catMeta.accent}`} />
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <CatIcon className="w-5 h-5 text-fg-teal" />
                    <h2 className="text-sm font-bold text-fg-navy uppercase tracking-wider">{catMeta.label}</h2>
                    <span className="text-xs text-fg-mid ml-auto">{catScenarios.length} scenario{catScenarios.length !== 1 ? 's' : ''}</span>
                  </div>

                  <div className="space-y-2">
                    {catScenarios.map((scenario) => (
                      <div key={scenario.id} id={`scenario-${scenario.id}`}>
                        <ScenarioCard
                          scenario={scenario}
                          isOpen={openIds.has(scenario.id)}
                          onToggle={() => toggle(scenario.id)}
                          onNavigate={navigateToScenario}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="card-static p-10 text-center">
          <QuestionMarkCircleIcon className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-fg-mid">No scenarios match your search. Try a different keyword.</p>
        </div>
      )}

      {/* Quick navigation to app sections */}
      <div className="card-static overflow-hidden mt-8">
        <div className="h-1 bg-gradient-to-r from-fg-teal to-fg-green" />
        <div className="p-5">
          <h3 className="text-sm font-bold text-fg-navy uppercase tracking-wider mb-3">Quick Links</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { label: 'Dashboard', path: '/' },
              { label: 'Projects', path: '/projects' },
              { label: 'Review Queue', path: '/reviews' },
              { label: 'Knowledge Base', path: '/knowledge' },
            ].map((link) => (
              <button
                key={link.path}
                onClick={() => navigate(link.path)}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-fg-dark hover:border-fg-teal hover:text-fg-teal transition-all"
              >
                {link.label}
                <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
