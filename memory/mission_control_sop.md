# Mission Control SOP (Standard Operating Procedure)

**Project:** Mission Control (Professor Hamada's Dashboard)
**Goal:** Modular, Token-Efficient, Safety-First Development
**Loop:** A (Builder) -> B (Critic) -> C (Architect/User)

---

## 🔄 The A/B/C Loop

### 1. Architect (User/Main Agent) initiates
- Defines the task (e.g., "Add a dark mode toggle").
- Loads `memory/mission_control_builder_prompt.md` into the context.
- Invokes **Builder**.

### 2. Phase A: Builder (Implementation)
- **Action**: Reads minimal context, locates code, applies `edit`.
- **Constraint**: Must not output massive logs. Must verify syntax.
- **Output**: Ends with `>> [BUILDER_DONE] ... >>`.

### 3. Phase B: Critic (Review)
- **Trigger**: Sees `[BUILDER_DONE]`.
- **Action**: Audits the specific `edit` or file diff. Checks for security leaks and token waste.
- **Constraint**: If rejecting, must provide specific fix instructions.
- **Output**:
    - `>> [CRITIC_PASS] ... >>` (Proceed to User)
    - `>> [CRITIC_FAIL] ... >>` (Return to Builder)

### 4. Phase C: Architect (Deployment)
- **Trigger**: Sees `[CRITIC_PASS]`.
- **Action**: Commits to git, deploys (if applicable), or marks task complete in ROADMAP.

---

## 🪙 Token-Saving Protocols

### Reading Files
- ❌ **BAD**: `read("src/app.js")` (Reads entire file).
- ✅ **GOOD**: `exec("grep -nC 5 'function toggleTheme' src/app.js")` (Reads only relevant lines).
- ✅ **GOOD**: `read("src/app.js", offset=50, limit=20)` (Reads specific chunk).

### Writing Files
- ❌ **BAD**: `write("src/app.js", new_content_1000_lines)` (Rewrites everything).
- ✅ **GOOD**: `edit("src/app.js", old_str, new_str)` (Replaces only what changed).

### Logging
- ❌ **BAD**: "I have analyzed the code and here is the full AST..."
- ✅ **GOOD**: "Found function at line 45. Editing."

---

## 🛡 Safety & Rollback

1.  **Backup**: Before major refactors, `cp file.js file.js.bak`.
2.  **Validation**: If a build fails, `mv file.js.bak file.js` immediately.
3.  **Secrets**: Never commit `.env` or files containing keys.

## 📡 Handover Signals Reference

| Role | Signal | Meaning |
| :--- | :--- | :--- |
| **Builder** | `>> [BUILDER_DONE] Summary: ... >>` | Task attempted, ready for review. |
| **Critic** | `>> [CRITIC_PASS] ... >>` | Approved. Safe to deploy/merge. |
| **Critic** | `>> [CRITIC_FAIL] ... >>` | Rejected. Builder must retry. |
