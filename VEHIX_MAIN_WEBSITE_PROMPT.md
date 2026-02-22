# Vehix Professional Website Development Prompt

## Overview
Create a comprehensive, professional web application for the Vehix vehicle assistance platform. The website should serve as the primary user interface for riders, roadies (mechanics), and garage partners, featuring modern design, seamless user experience, and full integration with the existing Django backend APIs.

## Platform Summary
Vehix is a vehicle assistance service that connects riders (customers) with roadies (mobile mechanics) for on-demand vehicle services. The platform includes real-time location tracking, secure payments via PesaPal, chat functionality, and comprehensive admin management. Additional features include garage partnerships, referral programs, and multi-role user management.

## System Architecture

### Frontend Technology Stack
- **Framework**: React.js with TypeScript for type safety
- **State Management**: Redux Toolkit for complex state, Zustand for simpler components
- **Routing**: React Router v6 with protected routes
- **UI Library**: Material-UI (MUI) v5 with custom theming
- **HTTP Client**: Axios with interceptors for authentication and error handling
- **Real-time Communication**: Socket.IO client for WebSocket connections
- **Maps Integration**: Google Maps or Mapbox for location services
- **Form Handling**: React Hook Form with Yup validation
- **File Upload**: React Dropzone with progress indicators
- **Notifications**: React Toastify for user feedback
- **Charts/Data Visualization**: Chart.js or Recharts for analytics

### Backend Integration
- **API Base URL**: Configurable for different environments
- **Authentication**: JWT tokens with automatic refresh
- **Real-time Updates**: WebSocket connections for live tracking
- **File Storage**: Integration with backend media endpoints
- **Payment Processing**: PesaPal integration for deposits/withdrawals

## Core Features Implementation

### 1. Landing Page & Marketing

#### Hero Section
- **Dynamic Headlines**: Rotating service highlights ("Get Help Fast", "Expert Mechanics", "24/7 Support")
- **Call-to-Action Buttons**: "Book Service" and "Become a Roadie"
- **Background**: High-quality vehicle service imagery with overlay
- **Mobile-First Design**: Optimized for all screen sizes

#### Services Overview
- **Service Categories**: Visual cards for each service type (Towing, Battery Jump, Tire Change, etc.)
- **Pricing Display**: Transparent pricing with base fees
- **How It Works**: 3-step process visualization
  1. Request Service
  2. Track Roadie
  3. Get Help

#### Trust Indicators
- **Statistics**: "10,000+ Services Completed", "4.8★ Rating", "50+ Cities Covered"
- **Testimonials**: Customer reviews with photos
- **Partner Logos**: Garage and service partner badges
- **Security Badges**: SSL encryption, verified mechanics

#### Footer
- **Quick Links**: Services, About, Support, Partners
- **Contact Information**: Phone, email, social media
- **Newsletter Signup**: Email collection for updates
- **Legal Links**: Terms, Privacy, Cookies

### 2. User Authentication & Onboarding

#### Registration Flow
- **Multi-Role Selection**: Rider, Roadie, or Garage Partner
- **Step-by-Step Forms**:
  - Basic Information (Name, Email, Phone)
  - Location & Preferences
  - KYC Documents (ID, Profile Photo)
  - Service Preferences (for Roadies)
- **OTP Verification**: SMS/phone verification for account security
- **Referral Code**: Optional field for referral tracking

#### Login Options
- **Standard Login**: Username/password with "Remember Me"
- **Social Login**: Google, Facebook integration (optional)
- **Biometric Login**: Fingerprint/face ID on mobile devices
- **Password Recovery**: Secure reset with OTP

#### Profile Completion
- **Progress Indicator**: Show completion percentage
- **Required vs Optional**: Clear distinction for mandatory fields
- **Document Upload**: Support for ID, license, certificates
- **Approval Status**: Real-time status updates for account verification

### 3. Service Booking System

#### Service Selection
- **Category Browser**: Filter by service type, vehicle type, urgency
- **Location Input**: GPS detection or manual address entry
- **Service Details**: Description, estimated time, pricing
- **Urgency Options**: Standard, Priority, Emergency pricing

#### Roadie Matching
- **Real-time Search**: Show available roadies in the area
- **Roadie Profiles**: Rating, experience, services offered
- **ETA Calculation**: Distance and time estimates
- **Price Quotes**: Dynamic pricing based on service and distance

#### Booking Confirmation
- **Service Summary**: All details before confirmation
- **Payment Preview**: Total cost breakdown
- **Cancellation Policy**: Clear terms displayed
- **Booking Reference**: Unique tracking number

### 4. Real-Time Tracking & Communication

#### Live Tracking Interface
- **Map Integration**: Google Maps with real-time roadie location
- **Status Updates**: Visual progress indicators (Requested → Accepted → En Route → Arrived → In Progress → Completed)
- **ETA Updates**: Dynamic time remaining calculations
- **Route Visualization**: Show roadie's path to destination

#### In-App Communication
- **Chat Interface**: Real-time messaging with roadie
- **Voice Calls**: Integration with WebRTC (optional)
- **Photo Sharing**: Send/receive images during service
- **Service Updates**: Automated status messages

#### Notification System
- **Push Notifications**: Browser and mobile push alerts
- **SMS Alerts**: Critical updates via SMS
- **Email Notifications**: Service confirmations and receipts
- **In-App Notifications**: Bell icon with unread count

### 5. User Dashboard

#### Rider Dashboard
- **Active Requests**: Current service status and tracking
- **Service History**: Past services with ratings and receipts
- **Wallet Balance**: Current balance and transaction history
- **Favorites**: Saved roadies and preferred services
- **Profile Settings**: Account management and preferences

#### Roadie Dashboard
- **Service Requests**: Incoming requests with accept/decline
- **Earnings Tracker**: Daily/weekly/monthly earnings
- **Service History**: Completed jobs with ratings
- **Availability Toggle**: Online/offline status control
- **Performance Metrics**: Rating, completion rate, response time

#### Wallet & Payments
- **Balance Display**: Current wallet balance prominently shown
- **Transaction History**: Detailed list with filters
- **Deposit Options**: PesaPal integration with STK push
- **Withdrawal Requests**: Secure withdrawal to mobile money
- **Payment Methods**: Multiple options (M-Pesa, Airtel Money, etc.)

### 6. Integrated Garage Onboarding

#### Partner Registration
- **Multi-Step Application**: 10-step process as per existing prompt
- **Document Management**: Secure upload and verification
- **Status Tracking**: Real-time application progress
- **Support Chat**: Direct communication with support team

#### Partner Portal
- **Business Dashboard**: Service requests, earnings, customers
- **Staff Management**: Add/manage mechanics
- **Service Configuration**: Pricing, availability, specialties
- **Analytics**: Performance metrics and insights

### 7. Referral & Rewards System

#### Referral Program
- **Unique Codes**: Personal referral links and codes
- **Reward Tracking**: Earned credits and pending rewards
- **Social Sharing**: Easy share buttons for social media
- **Leaderboard**: Top referrers with rewards

#### Loyalty Program
- **Points System**: Earn points for services and referrals
- **Reward Redemption**: Convert points to wallet credit
- **Tier Benefits**: Different levels with perks
- **Special Offers**: Exclusive deals for loyal users

## Technical Implementation Details

### API Integration Points

#### Authentication APIs
```javascript
POST /api/register/          // User registration
POST /api/login/             // User login
POST /api/refresh/           // Token refresh
GET  /api/me/                // User profile
```

#### Service Request APIs
```javascript
POST /api/requests/create/   // Create service request
GET  /api/requests/my/       // User's requests
POST /api/requests/{id}/accept/    // Accept request (Roadie)
POST /api/requests/{id}/cancel/    // Cancel request
```

#### Real-time WebSocket Channels
```javascript
/ws/rider/                   // Rider tracking channel
/ws/rodie/                   // Roadie offers channel
/ws/availability/           // Nearby roadies
```

#### Payment APIs
```javascript
GET  /api/wallet/            // Wallet balance
POST /api/wallet/deposit/    // Initiate deposit
POST /api/wallet/withdraw/   // Request withdrawal
```

### Responsive Design Requirements

#### Mobile Optimization
- **Touch-Friendly**: Large buttons and touch targets
- **Native Feel**: iOS/Android design patterns
- **Offline Support**: Basic functionality without internet
- **GPS Integration**: Automatic location detection

#### Tablet Support
- **Adaptive Layouts**: Optimized for tablet screens
- **Multi-Panel Views**: Side-by-side information display
- **Touch Gestures**: Swipe actions for navigation

#### Desktop Enhancement
- **Multi-Column Layouts**: Efficient use of screen space
- **Keyboard Shortcuts**: Power user features
- **Hover States**: Enhanced interactivity
- **Advanced Features**: Additional tools and analytics

### Performance Requirements

#### Loading Times
- **Initial Load**: < 3 seconds
- **Page Transitions**: < 1 second
- **API Responses**: < 500ms average
- **Image Loading**: Progressive loading with lazy loading

#### Caching Strategy
- **Static Assets**: Long-term caching with versioning
- **API Data**: Intelligent caching with invalidation
- **Offline Data**: Critical data available offline
- **Service Worker**: Background sync and push notifications

#### Scalability Considerations
- **Code Splitting**: Route-based and component-based splitting
- **Image Optimization**: WebP format with fallbacks
- **Bundle Analysis**: Regular bundle size monitoring
- **CDN Integration**: Global content delivery

### Security Implementation

#### Data Protection
- **HTTPS Only**: SSL/TLS encryption for all communications
- **Input Validation**: Client and server-side validation
- **XSS Prevention**: Sanitization of user inputs
- **CSRF Protection**: Token-based protection

#### Authentication Security
- **JWT Security**: Secure token storage and automatic refresh
- **Session Management**: Secure logout and session timeout
- **Password Policies**: Strong password requirements
- **Two-Factor Authentication**: SMS-based 2FA option

#### Payment Security
- **PCI Compliance**: Secure payment processing
- **Tokenization**: Sensitive data never stored client-side
- **Fraud Detection**: Transaction monitoring
- **Secure Redirects**: Safe external payment flows

### Accessibility Features (WCAG 2.1 AA)

#### Visual Accessibility
- **Color Contrast**: Minimum 4.5:1 ratio
- **Font Scaling**: Support for 200% zoom
- **Focus Indicators**: Visible focus outlines
- **Alt Text**: Descriptive image alternatives

#### Motor Accessibility
- **Keyboard Navigation**: Full keyboard support
- **Touch Targets**: Minimum 44px touch targets
- **Gesture Alternatives**: Non-gesture alternatives
- **Time Limits**: Adjustable or removable timeouts

#### Cognitive Accessibility
- **Clear Language**: Simple, understandable text
- **Consistent Navigation**: Predictable interface patterns
- **Error Prevention**: Clear error messages and recovery
- **Help Documentation**: Context-sensitive help

## Testing & Quality Assurance

### Unit Testing
- **Component Tests**: Individual component functionality
- **Hook Tests**: Custom hooks and state management
- **Utility Tests**: Helper functions and utilities
- **API Integration Tests**: Mock API responses

### Integration Testing
- **User Flows**: Complete user journey testing
- **API Integration**: Real API endpoint testing
- **WebSocket Testing**: Real-time feature testing
- **Payment Flows**: Complete payment process testing

### End-to-End Testing
- **Critical Paths**: Registration to service completion
- **Cross-Browser**: Chrome, Firefox, Safari, Edge
- **Mobile Testing**: iOS Safari, Android Chrome
- **Performance Testing**: Load and stress testing

### User Acceptance Testing
- **Usability Testing**: Real user feedback sessions
- **Accessibility Testing**: Screen reader and keyboard testing
- **Performance Monitoring**: Real user monitoring (RUM)
- **A/B Testing**: Feature comparison and optimization

## Deployment & Maintenance

### Environment Setup
- **Development**: Local development with hot reload
- **Staging**: Pre-production testing environment
- **Production**: Live environment with monitoring
- **CI/CD Pipeline**: Automated testing and deployment

### Monitoring & Analytics
- **Performance Monitoring**: Page load times, API response times
- **Error Tracking**: Sentry integration for error reporting
- **User Analytics**: Google Analytics or Mixpanel
- **Business Metrics**: Conversion rates, user engagement

### Maintenance Tasks
- **Security Updates**: Regular dependency updates
- **Performance Optimization**: Continuous performance monitoring
- **Feature Updates**: Regular feature releases
- **User Support**: Help desk integration

## Success Metrics

### User Experience Metrics
- **Conversion Rate**: Visitor to registered user
- **Service Completion Rate**: Request to completed service
- **User Retention**: Repeat usage over time
- **Customer Satisfaction**: Ratings and feedback scores

### Technical Metrics
- **Page Load Times**: < 3 seconds average
- **API Response Times**: < 500ms average
- **Error Rates**: < 1% of all requests
- **Uptime**: 99.9% availability

### Business Metrics
- **Monthly Active Users**: User engagement tracking
- **Service Volume**: Number of services completed
- **Revenue Growth**: Monthly recurring revenue
- **Partner Growth**: Number of active roadies/garages

This comprehensive prompt provides the foundation for building a world-class vehicle assistance platform website that matches the sophistication of modern ride-sharing and service platforms like Uber, Lyft, or TaskRabbit, while incorporating the unique features of the Vehix ecosystem.
