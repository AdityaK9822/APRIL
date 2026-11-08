 `# Guide: Creating High-Quality Engineering Issues

This document serves as a reference for creating detailed, actionable engineering issues for the APRIL Agent project. Following this structure ensures that any AI agent or human developer can implement the task without ambiguity, without touching unrelated files, and with clear safety boundaries.

## 1. Issue Structure (The Template)

Every technical issue should follow this exact layout:

### 🏷️ Metadata
- **Title**: `[Prefix-ID] Concise Action-Oriented Summary` (e.g., `H-1: Initialize uv project`)
- **Labels**: `area: [component]`, `priority: [p0/p1/p2]`, `[reference-repo-tag]`

### 👤 Role & Context
- **Role**: The specific persona required for the task (e.g., *Senior Python DevOps Engineer*, *Security Engineer*).
- **Context from docs**: Explicitly list which \`.md\` files the agent must read before starting to understand the architectural scope.

### 🎯 Scope of Work
- **Modify**: Exact list of files to be changed.
- **Create**: Exact paths for new files.
- **Do NOT touch**: A strict list of directories or files that must remain untouched to prevent "scope creep" or accidental regressions.

### 🚧 Constraints & Guardrails
- **Constraints**: Hard technical requirements (e.g., *Must use Python 3.12*, *No third-party libraries*).
- **Strict Guardrails**: Safety checks that must pass. These are "fail-fast" conditions (e.g., *Succeeds in \`ruff check\`*, *No path escapes allowed*).

### 📝 Technical Description
A detailed explanation of *what* needs to be implemented and *how* it fits into the larger system. Include specific class names, function signatures, or logic flows.

### ✅ Acceptance Criteria
A checklist of measurable results that prove the issue is complete.

### 🔗 Dependencies & DoD
- **Dependencies**: Which issue numbers must be closed before this one can start.
- **Definition of Done (DoD)**: The final state of the repository (e.g., *Tests pass, docs updated, linting clean*).

---

## 2. How to Create Issues using GitHub CLI (\`gh\`)

To avoid manual entry and ensure consistency, use the GitHub CLI.

### Basic Command
\`\`\`bash
gh issue create --title "Title here" --body "Body content here" --label "label1" --label "label2"
\`\`\`

### Pro Tips for Power Users

#### 1. Using Multi-line Body
When creating issues from a terminal, use quotes to preserve line breaks:
\`\`\`bash
gh issue create --title "H-1: Setup" --body "
**Role**: DevOps
**Scope**:
- Modify pyproject.toml
" --label "priority: p0"
\`\`\`

#### 2. Creating Issues in Batch (Scripting)
If you have a long list of issues, use a shell loop:
\`\`\`bash
for i in {1..10}; do
  gh issue create --title "Issue $i" --body "Description for $i" --label "area: core"
done
\`\`\`

#### 3. Useful \`gh\` Commands for Issue Management
- **List issues**: \`gh issue list\`
- **View specific issue**: \`gh issue view <number>\`
- **Edit issue title**: \`gh issue edit <number> --title "New Title"\`
- **Add label to issue**: \`gh issue edit <number> --add-label "new-label"\`
- **Close issue**: \`gh issue close <number>\`
`