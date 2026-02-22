# Garage Onboarding Website Development Prompt

## Overview
Create a comprehensive web application for garage partners to apply for registration with Vehix, featuring a multi-step form flow similar to passport/visa application systems. The application should include cascading dropdowns for location selection and a robust status tracking system.

## System Architecture

### Frontend Technology Stack
- **Framework**: React.js with TypeScript
- **State Management**: Redux Toolkit or Zustand
- **Routing**: React Router v6
- **UI Library**: Material-UI (MUI) or Ant Design
- **Form Handling**: React Hook Form with validation
- **HTTP Client**: Axios with interceptors
- **File Upload**: React Dropzone or similar
- **Maps Integration**: Google Maps or OpenStreetMap for location selection

### Backend Integration
- **API Base URL**: `/api/garages/`
- **Authentication**: JWT tokens (existing user system)
- **File Storage**: Cloud storage (AWS S3, Google Cloud Storage, or similar)

## Application Flow Structure

### Step-by-Step Form Process

#### Step 1: Application Type Selection
**Page**: `/apply`
- Garage Type Selection:
  - Individual / Informal Garage
  - Registered Business
- Terms and Conditions Acceptance
- Privacy Policy Agreement
- Contact Information Collection (Email for notifications)

#### Step 2: Basic Information
**Page**: `/apply/basic-info`
- Garage Name (as publicly displayed)
- Years in Operation
- Physical Address (with GPS coordinates)
- Operating Hours (per day of week)
- Primary Phone Number (OTP verification)
- Secondary Phone Number (optional)
- Business Email Address

#### Step 3: Ownership & Management
**Page**: `/apply/ownership`
- Owner Full Name
- National ID / Passport Number
- ID Document Upload (Front & Back)
- Owner Phone Number (OTP verification)
- Owner Email Address
- Emergency Contact (Name & Phone)
- Manager Details (if different from owner)

#### Step 4: Location Details
**Page**: `/apply/location`
- **Cascading Dropdown System**:
  1. Country Selection → Populates Districts
  2. District Selection → Populates Sub-counties/Counties
  3. Sub-county Selection → Populates Parishes/Divisions
  4. Parish Selection → Populates Villages/Localities

- GPS Coordinates (auto-captured or manual entry)
- Service Coverage Area (radius selection on map)

#### Step 5: Workshop Verification
**Page**: `/apply/workshop`
- Exterior Photo Upload (Garage signboard visible)
- Interior Workshop Photo
- Tools & Equipment Photo (optional)
- Workshop Description
- Parking Capacity
- Workshop Size (sq meters)

#### Step 6: Services & Pricing
**Page**: `/apply/services`
- **Vehicle Types Supported** (Multi-select):
  - Motorcycles
  - Cars
  - Vans
  - Trucks

- **Service Categories** (Multi-select with sub-services):
  - Engine Repair (Oil change, Engine overhaul, etc.)
  - Brake Service (Pad replacement, Disc turning, etc.)
  - Electrical & Diagnostics (Battery testing, ECU scanning, etc.)
  - Tire & Wheel Services (Tire fitting, Balancing, etc.)
  - Body Work & Painting (Dent removal, Painting, etc.)
  - Routine Servicing (Full service, Interim service, etc.)
  - Accident Repair (Panel beating, Frame straightening, etc.)

- **Pricing Structure**:
  - Base prices for each service
  - Inspection/diagnostic fees
  - Emergency service pricing
  - Negotiable pricing toggle

#### Step 7: Staff & Qualifications
**Page**: `/apply/staff`
- Number of Mechanics
- Lead Mechanic Details (Name, Experience, Certifications)
- Staff Certifications Upload
- Specialized Skills
- Training Records

#### Step 8: Business Documents
**Page**: `/apply/documents`
- **Conditional Documents Based on Garage Type**:
  - **For Registered Businesses**:
    - Business Registration Certificate
    - TIN/Tax ID Certificate
    - Trading License
    - Company Memorandum & Articles

  - **For Individual Garages**:
    - Owner National ID (already uploaded)
    - Local Authority Letter (optional)
    - Workshop Lease Agreement (optional)

- Document Format Support: PDF, JPG, PNG (Max 5MB each)
- Preview functionality before upload

#### Step 9: Policies & Banking
**Page**: `/apply/policies`
- Service Policies:
  - Warranty Offered (Yes/No)
  - Warranty Duration (if yes)
  - Average Turnaround Time
  - Emergency Service Availability
  - Working Days Selection
  - Cancellation Policy

- Banking Information:
  - Payment Method (Mobile Money / Bank Transfer)
  - Account Holder Name
  - Account Number
  - Provider Name (MTN, Airtel, Bank Name)
  - Settlement Preference (Daily/Weekly)

#### Step 10: Review & Submit
**Page**: `/apply/review`
- Complete Application Summary
- Edit buttons for each section
- Terms Acceptance Checkbox
- Digital Signature Capture
- Final Submission

## Status Tracking System

### Application Status Page
**Page**: `/status`
- Tracking ID Input Field
- Status Display with Progress Indicator
- Detailed Status Information:
  - Current Status (Submitted, Under Review, Verified, Rejected, Suspended)
  - Submission Date
  - Last Updated
  - Expected Processing Time
  - Next Steps

### Status Types & Messages
- **SUBMITTED**: "Your application has been received and is being reviewed."
- **UNDER_REVIEW**: "Our team is currently reviewing your application documents."
- **VERIFIED**: "Congratulations! Your garage has been verified and is now active."
- **REJECTED**: "Application was not approved. Reason: [Detailed reason]"
- **SUSPENDED**: "Your garage account has been suspended. Reason: [Detailed reason]"

### Status Update Notifications
- Email notifications for status changes
- In-app notifications (if user logged in)
- SMS alerts for critical updates

## Cascading Dropdown Implementation

### Location Data Structure
```javascript
const locationData = {
  uganda: {
    districts: {
      "kampala": {
        subcounties: ["Central Division", "Kawempe", "Makindye", "Nakawa", "Rubaga"],
        parishes: {
          "Central Division": ["Nakasero", "Nakivubo", "Namirembe"],
          // ... more parishes
        }
      },
      // ... more districts
    }
  },
  // ... more countries
}
```

### Implementation Requirements
1. **Lazy Loading**: Load location data on demand to reduce initial bundle size
2. **Search Functionality**: Allow typing to search locations
3. **Validation**: Ensure selected locations are valid combinations
4. **GPS Integration**: Option to auto-detect location
5. **Offline Support**: Cache frequently used locations

## Technical Requirements

### Form Validation Rules
- Required field validation
- Email format validation
- Phone number format validation (international)
- File type and size validation
- Conditional validation based on selections
- Cross-field validation (e.g., warranty duration required if warranty offered)

### File Upload Specifications
- **Image Files**: JPG, PNG, WebP (Max 5MB)
- **Document Files**: PDF, DOC, DOCX (Max 10MB)
- **Multiple File Upload**: Support for batch uploads
- **Progress Indicators**: Upload progress bars
- **Error Handling**: Clear error messages for failed uploads

### Responsive Design Requirements
- **Mobile-First Approach**: Optimized for mobile devices
- **Tablet Support**: Dedicated tablet layouts
- **Desktop Enhancement**: Additional features for larger screens
- **Accessibility**: WCAG 2.1 AA compliance
- **Cross-Browser Support**: Chrome, Firefox, Safari, Edge

### Performance Requirements
- **Initial Load**: < 3 seconds
- **Form Steps**: < 1 second transitions
- **File Upload**: Progress feedback
- **Search/Autocomplete**: < 300ms response time
- **Offline Capability**: Basic form saving

## API Integration Points

### Registration API
```javascript
POST /api/garages/register/
Content-Type: multipart/form-data

// Multi-part form data with all fields
```

### Status Check API
```javascript
POST /api/garages/check-status/
{
  "application_tracking_id": "VX00123456"
}
```

### File Upload API
```javascript
POST /api/garages/upload-document/
Content-Type: multipart/form-data
{
  "document_type": "business_registration",
  "file": [file]
}
```

## User Experience Considerations

### Progressive Disclosure
- Show only relevant fields based on previous selections
- Conditional sections that appear/hide dynamically
- Smart defaults based on user selections

### Error Handling & Feedback
- Real-time validation feedback
- Clear error messages with suggestions
- Recovery options for failed submissions
- Save draft functionality

### Accessibility Features
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode support
- Alternative text for images
- Focus management

## Security Considerations

### Data Protection
- SSL/TLS encryption for all data transmission
- Secure file storage with access controls
- GDPR compliance for data handling
- Regular security audits

### Authentication & Authorization
- JWT token-based authentication
- Role-based access control
- Session management
- Secure logout functionality

## Testing Requirements

### Unit Tests
- Form validation logic
- API integration
- File upload functionality
- Cascading dropdown logic

### Integration Tests
- Complete application flow
- API error handling
- File upload and processing

### User Acceptance Testing
- End-to-end application submission
- Status tracking functionality
- Mobile responsiveness
- Accessibility compliance

## Deployment & Maintenance

### Environment Setup
- Development, Staging, Production environments
- CI/CD pipeline configuration
- Automated testing integration
- Monitoring and logging setup

### Maintenance Tasks
- Regular security updates
- Performance monitoring
- User feedback collection
- Feature enhancement planning

## Success Metrics

### User Experience Metrics
- Application completion rate
- Average time to complete application
- User satisfaction scores
- Error rate during submission

### Technical Metrics
- Page load times
- API response times
- File upload success rate
- System uptime

This comprehensive prompt should enable the development of a professional, user-friendly garage onboarding system that matches the quality and functionality of government application portals.
