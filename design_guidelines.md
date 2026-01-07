# FOTO VIDEO MOJICA Job Management System - Design Guidelines

## Design Approach
**System:** Bootstrap 5 Dark Theme with custom enhancements for photography business identity
**Justification:** Dark theme reduces eye strain during extended work sessions, provides professional aesthetic for creative agency, and makes photography thumbnails pop visually.

## Core Design Elements

### Typography
- **Primary Font:** Inter (Google Fonts) - clean, professional for UI
- **Accent Font:** Montserrat for headings and branding
- **Hierarchy:** 
  - Page titles: 2rem/bold
  - Section headers: 1.5rem/semibold
  - Body/data: 1rem/regular
  - Captions/metadata: 0.875rem/regular

### Layout System
**Spacing:** Standardize on Bootstrap units: 2, 3, 4, 6, 8 (p-2, m-3, gap-4, py-6, mb-8)
**Container Strategy:** fluid-containers with max-width breakpoints, consistent 24px gutters

### Dashboard Architecture

**Sidebar Navigation (Persistent):**
- Width: 280px desktop, collapsible to 60px icons-only, off-canvas mobile
- Branding: FOTO VIDEO MOJICA logo at top (240x60px)
- Role-based menu items with icons
- User profile card at bottom with role badge
- Active state: subtle border-left accent

**Top Bar:**
- Search bar (global jobs/clients search)
- Notifications bell with count badge
- Quick actions dropdown (New Job, New Client)
- User avatar with dropdown menu

**Main Content Area:**
- Page header with title, breadcrumbs, primary action button
- Content cards with rounded corners (8px), subtle shadows
- Data tables with zebra striping, hover states, sorting indicators

### Component Library

**Job Cards:**
- Thumbnail preview (photography work) - 120x80px
- Client name, job type, status badge, due date
- Quick action buttons (Edit, View Details, Mark Complete)
- Status: Color-coded badges (Pending/In Progress/Review/Complete)

**Employee Metrics Dashboard:**
- Summary cards: Total Jobs, Completion Rate, Average Rating, Current Streak
- Monthly performance chart (line/bar hybrid)
- Employee of Month podium display with profile photos
- PDF report upload zone with drag-drop interface

**Data Tables:**
- Fixed header on scroll
- Column sorting with arrow indicators
- Row actions menu (three-dot icon)
- Inline editing for quick updates
- Pagination with item count display

**Forms:**
- Floating labels pattern
- Input groups for related fields
- File upload with preview thumbnails
- Validation states with inline error messages
- Multi-step forms with progress indicator

**Role-Based Elements:**
- Admin: Full CRUD, Employee of Month module, PDF analysis tools
- Manager: Job assignment, team performance view, report generation
- Employee: Job list, personal metrics, time tracking

### Images
**Profile Photos:** Employee headshots in circular frames (80x80px dashboard, 200x200px Employee of Month showcase)
**Job Thumbnails:** Photography work previews in 16:10 ratio cards
**Empty States:** Custom illustrations for "No jobs assigned," "Upload your first report"
**No hero image** - this is a dashboard application

### Navigation Patterns
- Breadcrumb trail below top bar
- Tab navigation for multi-section pages (Job Details: Info/Files/Timeline/Comments)
- Drawer pattern for filters (slide-in from right)
- Modal dialogs for create/edit forms

### Mobile Optimization
- Bottom navigation bar (5 primary functions)
- Swipe actions on cards (swipe right: edit, left: complete)
- Simplified tables with expandable rows
- Touch-optimized 48px minimum tap targets
- Collapsible sections with accordion pattern

### Data Visualization
- Completion trend charts (7-day, 30-day, 90-day views)
- Job distribution pie charts
- Employee performance comparison bar charts
- PDF analysis results in visual summaries (extracted metrics from reports)

### Animations
**Minimal approach:**
- Smooth page transitions (200ms ease)
- Loading skeleton screens for data fetch
- Success confirmations (check mark animation, toast notifications)
- No decorative animations

**Critical UX Indicators:**
- Disabled state opacity reduction
- Form validation shake effect on error
- Drag-drop hover states with scale transform

This design prioritizes information density, workflow efficiency, and role-appropriate access while maintaining visual consistency with Bootstrap's dark theme foundations. The photography business context is honored through curated imagery integration without compromising dashboard functionality.