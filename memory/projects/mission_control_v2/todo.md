# Mission Control V2 Implementation Plan

**Goal:** Evolve the current research dashboard into a high-performance, secure, and visually stunning "Cockpit" for Professor Hamada.

## 🛠 Specifications (Target V2)
1. **Visual Style**: "Midnight Cockpit" - Dark mode base, Tailwind CSS, Glassmorphism, cyan/violet accents. High information density with clean typography.
2. **Research Integration**: Primary focus on `mhamada-research` Organization. Dynamic links to MCTO, Natto, and Neuro projects.
3. **Security**: Absolute separation between `memory/` (private) and `site-public/` (public). Public site only fetches sanitized `.json` files.
4. **Responsive**: Mobile-first design for checking status on the go.

## 📋 Task List

### Phase 1: Planning & Setup
- [ ] Initialize project directory and define core UI components.
- [ ] Create `critic-ai` sub-agent for review.

### Phase 2: Core UI Overhaul
- [ ] **index.html**: Redesign as a central command hub.
    - Add "System Health" monitor (Gateway status, Version, Memory load).
    - Add "Active Projects" grid linking to GitHub repositories.
- [ ] **tasks.html**: Implement "Combat Task Board" (Dark mode, priority levels).
- [ ] **calendar.html**: Integrated timeline view of schedules and AI cron jobs.
- [ ] **office.html**: Enhance Digital Office with real-time status and animal avatars (Cockpit version).

### Phase 3: Data & Security
- [ ] Verify `sync_tasks.js` and other scripts output to `site-public/*.json` only.
- [ ] Remove any direct links to internal `memory/*.md` files from public HTML.

### Phase 4: Final Polishing
- [ ] Cross-browser testing (Chrome/Safari/Mobile).
- [ ] Vercel Production Deploy.

---

## 🔍 Review Board
- **Critic AI Verdict**: [Pending]
- **Architect (Bot) Notes**: Focus on "Elegance" and "Speed". Use local Gemini 3 for generation tasks.

---
Created: 2026-02-23 22:00 JST
@Bot
