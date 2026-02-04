# Overview

This is a job management system for "FOTO VIDEO MOJICA", a photography and video business. The system handles the complete workflow from job registration to completion and delivery, with role-based access control for administrators, supervisors, and designers. It includes features for inventory management, QR code scanning, WhatsApp notifications, invoice generation, and real-time messaging between users.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

## February 2026 - Public Client Portal
- Created public portal at /cliente for clients to view their photos
- Login requires invoice number + last 4 digits of phone (security verification)
- Different states handled: working, no_photos, payment_required, photos_ready
- Photos uploaded by designers are now directly available (no verification needed)
- Access expires when job is marked as delivered
- If payment pending (total - deposit > 0): photos blocked until paid
- If no photos uploaded: redirects to WhatsApp +18092460263
- Modified send_job_photos to save directly to CompletedJob

## January 2026 - Employee of the Month Module
- Added "Empleado del Mes" module for calculating employee production from PDF reports
- New EmployeeOfMonthReport model to store historical reports
- Created admin_or_yimi_required decorator for special access (Admin + Yimi supervisor)
- PDF parsing with pdfplumber to extract 5x7 photos and combos data
- Combo equivalencies: Bebé=4, Cumpleaños=6, Embarazada=11, 15 Años=13, Navidad/Oferta=8
- PDF report generation with ReportLab showing winner highlighted
- Module visible in menu only for Admin and user "Yimi"

## August 2025 - Firebase Cloud Messaging Implementation
- Implemented comprehensive Firebase Cloud Messaging system for internal staff notifications
- Added fcm_token field to User model for push notification support
- Created Firebase configuration files and notification utilities
- Implemented automatic notifications every 40 minutes for designers with pending work
- Added "Notificar" button in designer dashboard to mark work ready for verification
- Added congratulatory notifications and modal when supervisors approve work
- Integrated Firebase notifications into job approval workflow
- Created comprehensive notification system with foreground and background message handling
- Updated base template to include Firebase SDK and initialization scripts
- Added automatic notification permission request on first login with immediate welcome notification
- Implemented supervisor notifications when designers mark work ready for verification

## August 2025 - WhatsApp Integration Simplification
- Removed Twilio WhatsApp bulk notification system due to configuration issues
- Simplified WhatsApp integration to use web links instead of API calls
- Unified invoice and WhatsApp buttons into single functionality
- Removed purple "notificar" button
- Added "undo" functionality for jobs marked as "called"
- Updated WhatsApp message format to include business contact information
- Added close button to invoice interface
- Fixed WhatsApp button to properly use phone number from invoice
- Separated invoice messages from work completion messages:
  * Invoice messages: Include contact numbers and explain it's a virtual copy
  * Work completion messages: No contact numbers, simpler notification format

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM for database operations
- **Database**: PostgreSQL with Alembic migrations for schema management
- **Authentication**: Flask-Login with role-based access control (Admin, Supervisor, Designer)
- **Session Management**: File-based sessions with 7-day persistence
- **Real-time Features**: Server-Sent Events (SSE) for live notifications and updates

## Data Models
- **User System**: Multi-role user authentication with hierarchical permissions
- **Job Workflow**: Complete job lifecycle from pending → completed → delivered states
- **Inventory Management**: Product tracking with QR code integration for withdrawals
- **Activity Logging**: Comprehensive audit trail for all system actions
- **Messaging System**: Internal communication between users with read status tracking

## Frontend Architecture
- **Progressive Web App (PWA)**: Offline-capable with service worker for mobile experience
- **Responsive Design**: Bootstrap-based dark theme optimized for mobile devices
- **Interactive Components**: DataTables for data management, real-time notifications
- **QR Code Integration**: HTML5 QR scanner for inventory management

## Key Features
- **Job Management**: Complete workflow from registration to delivery with approval processes
- **Invoice System**: PDF generation with QR codes for job verification
- **WhatsApp Integration**: Automated client notifications via Twilio API
- **Inventory Control**: QR-based product tracking and withdrawal system
- **Photo Gallery**: Secure temporary links for client photo access
- **Real-time Notifications**: Live updates across all connected users

## Security Implementation
- **Role-based Access Control**: Hierarchical permissions (Admin > Supervisor > Designer)
- **Session Security**: Secure session management with configurable expiration
- **Input Validation**: Server-side validation for all user inputs
- **Activity Monitoring**: Comprehensive logging of all system interactions

# External Dependencies

## Third-party Services
- **Firebase Cloud Messaging**: Real-time push notifications for internal staff communication
- **Twilio**: WhatsApp Business API for individual client notifications via web links
- **Redis**: Caching and real-time event streaming for SSE functionality

## Database
- **PostgreSQL**: Primary database with connection pooling and automatic reconnection

## Python Libraries
- **Flask Ecosystem**: Core framework with extensions for authentication, migrations, and SSE
- **Image Processing**: Pillow for logo processing and QR code generation
- **PDF Generation**: ReportLab and WeasyPrint for invoice and report generation
- **Communication**: Twilio SDK for WhatsApp messaging integration
- **Security**: JWT for temporary link generation and Werkzeug for password hashing

## Frontend Libraries
- **Bootstrap**: UI framework with dark theme for consistent styling
- **DataTables**: Advanced table functionality with sorting and filtering
- **HTML5-QRCode**: Client-side QR code scanning capabilities
- **Service Worker**: PWA functionality for offline access and app-like experience