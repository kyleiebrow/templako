# Lako - GPS Proximity Discovery of Micro-Retail Vendors

A comprehensive marketplace platform that connects customers with nearby micro-retail vendors using GPS technology, featuring real-time location tracking, vendor discovery, product management, and social features.

## Features

### Core Functionality
- **GPS-Based Vendor Discovery**: Real-time location tracking with proximity-based vendor search
- **Heatmap Visualization**: Interactive heatmaps showing vendor foot traffic and popularity
- **Vendor Profiles**: Detailed vendor information with products, ratings, and contact details
- **Product Management**: Full CRUD operations for vendor product catalogs
- **Customer Reviews**: Rating and review system for vendors
- **Social Feed**: Community posts, likes, and comments
- **Dual Database Architecture**: SQLite (primary) + Supabase (sync) for reliability

### Authentication & Security
- **OTP Email Verification**: Secure email-based authentication for all users
- **Role-Based Access**: Customer, Vendor, and Admin roles with appropriate permissions
- **Session Management**: Secure session handling with token-based authentication

### User Experience
- **Progressive Web App (PWA)**: Installable app with offline capabilities
- **Responsive Design**: Mobile-first design optimized for all devices
- **Guest Mode**: Browse vendors and feed without registration
- **Real-time Updates**: Live vendor data and location updates

### Admin Features
- **User Management**: View, suspend, and delete user accounts
- **Vendor Oversight**: Monitor and deactivate vendor accounts
- **Platform Statistics**: Comprehensive analytics and metrics

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (primary) + Supabase (PostgreSQL)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Mapping**: Leaflet.js with OpenStreetMap
- **Authentication**: OTP via SMTP email
- **Caching**: Custom decorator for API response caching
- **Deployment**: Render.com ready

## Installation

### Prerequisites
- Python 3.11+
- pip package manager

### Setup
1. Clone the repository:
```bash
git clone <repository-url>
cd templako
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-supabase-anon-key"
```

4. Run the application:
```bash
python backend/server.py
```

5. Open your browser to `http://localhost:5000`

## API Endpoints

### Authentication
- `POST /api/auth/register/customer` - Register as customer
- `POST /api/auth/register/vendor` - Register as vendor
- `POST /api/auth/login` - User login
- `POST /api/auth/verify-otp` - Verify email with OTP

### Customer APIs
- `GET /api/customer/map/vendors` - Get nearby vendors with products
- `GET /api/customer/map/vendor/<id>` - Get vendor details
- `POST /api/customer/reviews` - Submit vendor review

### Vendor APIs
- `GET /api/vendor/dashboard` - Get vendor dashboard stats
- `GET /api/vendor/catalog/products` - Get vendor products
- `POST /api/vendor/catalog/products` - Create product
- `PUT /api/vendor/catalog/products/<id>` - Update product
- `DELETE /api/vendor/catalog/products/<id>` - Delete product
- `GET /api/vendor/reviews` - Get vendor reviews

### Admin APIs
- `GET /api/admin/stats` - Get platform statistics
- `GET /api/admin/users` - Get all users
- `GET /api/admin/vendors` - Get all vendors
- `DELETE /api/admin/users/<id>` - Delete user
- `POST /api/admin/users/<id>/suspend` - Suspend user
- `POST /api/admin/vendors/<id>/deactivate` - Deactivate vendor

### Guest APIs
- `GET /api/guest/feed` - Get public feed posts

## Database Schema

### Users Table
- id, email, password, role, full_name, phone
- eula_accepted, eula_version, created_at
- otp_code, otp_expires, email_verified

### Vendors Table
- id, user_id, name, category, description
- address, latitude, longitude, rating, logo, phone, created_at

### Products Table
- id, vendor_id, name, description, category, price, image, created_at

### Reviews Table
- id, customer_id, vendor_id, rating, title, comment, created_at

### Messages, Posts, Likes, Comments Tables
- Full social media functionality support

## Deployment

### Render.com Deployment
1. Connect your GitHub repository to Render
2. Use the provided `render.yaml` configuration
3. Set environment variables in Render dashboard:
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

### Environment Variables
- `SMTP_USERNAME`: Gmail address for OTP emails
- `SMTP_PASSWORD`: Gmail app password (not regular password)
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase anon/public key

## Default Admin Account
- **Email**: admin@lako.com
- **Password**: admin123
- **Role**: Administrator

## Development

### Project Structure
```
templako/
├── backend/
│   └── server.py          # Main Flask application
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── README.md             # This file
└── logs/                 # Application logs
```

### Key Components
- **GPS Integration**: Real-time location detection with fallback
- **Heatmap Layer**: Dynamic vendor popularity visualization
- **OTP System**: Email-based verification for security
- **Caching Layer**: Performance optimization for API responses
- **Dual Database**: SQLite primary with Supabase sync for reliability

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is developed as a capstone project for AITE by:
- Kyle Brian M. Morillo
- Alexander Collin P. Millichamp

## Support

For questions or issues, please contact the development team.