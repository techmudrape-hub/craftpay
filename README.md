# 💰 CraftPay Platform

A secure and comprehensive payment gateway platform consisting of a merchant client portal, a secure admin dashboard, and a robust backend with JWT authentication, CAPTCHA verification, and comprehensive activity logging.

## ✨ Features

- 🔐 **Secure Authentication**: JWT token-based authentication with 1-hour expiration
- ⏱️ **Session Management**: Auto-expiry warning after 10 minutes of inactivity with 20-second countdown
- 🤖 **CAPTCHA Protection**: Visual CAPTCHA verification to prevent bot attacks
- 🔒 **Password Security**: Bcrypt hashing with salt for password storage
- 🚫 **Account Lockout**: Automatic lockout after 5 failed login attempts (15 minutes)
- 📊 **Activity Logging**: Complete audit trail with IP and user agent tracking
- 🎨 **Modern UI**: Beautiful, premium Light/Dark mode interface built with React and Tailwind CSS
- 🛡️ **Protected Routes**: Frontend route protection with token verification
- 🔄 **Session Refresh**: One-click session extension without re-login

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- MySQL Server (XAMPP/WAMP)

### Fastest Way to Start

**Windows Users:**
```bash
# Double-click START_HERE.bat
# Or run in terminal:
START_HERE.bat
```

**Manual Start:**

Terminal 1 (Backend):
```bash
cd backend
pip install -r requirements.txt
python app.py
```

Terminal 2 (Admin Frontend):
```bash
cd craftpay_admin
npm install
npm run dev
```

Terminal 3 (Client/Merchant Frontend):
```bash
cd craftpay_client
npm install
npm run dev
```

### Access the Application

- **Admin Portal**: http://localhost:5173
- **Merchant Portal**: http://localhost:5174 (or next available port)
- **Backend API**: http://localhost:5000
- **Health Check**: http://localhost:5000/api/admin/health

## 🔑 Default Credentials

- **Admin ID**: `6239572985`
- **Password**: `admin@123`

⚠️ **Change these in production!**

## 📁 Project Structure

```
Craftpay Dashboard/
├── backend/                      # Python Flask Backend
│   ├── app.py                   # Main application
│   ├── config.py                # Configuration
│   ├── database.py              # Database setup
│   ├── captcha_generator.py     # CAPTCHA generation
│   ├── requirements.txt         # Python dependencies
│   ├── .env                     # Environment variables
│   └── README.md
│
├── craftpay_admin/              # React Admin Frontend
│   ├── src/
│   │   ├── api/
│   │   │   └── admin_api.js    # API connector
│   │   ├── components/
│   │   │   ├── ui/             # UI components
│   │   │   └── ProtectedRoute.jsx
│   │   ├── pages/
│   │   │   ├── Login.jsx       # Login with CAPTCHA
│   │   │   ├── Dashboard.jsx
│   │   │   └── ...             # Management views
│   │   ├── layout/
│   │   └── App.jsx
│   └── package.json
│
├── craftpay_client/             # React Merchant Frontend
│   ├── src/                     # Merchant specific views and components
│   └── package.json
│
├── START_HERE.bat               # Quick start script
├── QUICK_START.md              # Quick start guide
├── SETUP_INSTRUCTIONS.md       # Detailed setup guide
├── SYSTEM_ARCHITECTURE.md      # Architecture documentation
└── README.md                   # This file
```

## 🔐 Security Features

| Feature | Description |
|---------|-------------|
| JWT Authentication | Token-based auth with 1-hour expiration |
| Session Expiry Warning | 10-minute timeout with 20-second warning |
| CAPTCHA Verification | Visual verification on login |
| Password Hashing | Bcrypt with salt |
| Account Lockout | 5 failed attempts = 15-minute lock |
| Activity Logging | Complete audit trail |
| Protected Routes | Frontend route protection |
| CORS Protection | Configured CORS policy |
| SQL Injection Prevention | Parameterized queries |
| Session Refresh | One-click session extension |

## 📡 API Endpoints

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/captcha` | Generate CAPTCHA |
| POST | `/api/admin/login` | Admin login |
| GET | `/api/admin/health` | Health check |

### Protected Endpoints (Require JWT)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/verify` | Verify JWT token |
| POST | `/api/admin/logout` | Admin logout |
| GET | `/api/admin/activity-logs` | Get activity logs |

## 🗄️ Database Schema

### admin_users
```sql
CREATE TABLE admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    login_attempts INT DEFAULT 0,
    locked_until TIMESTAMP NULL
);
```

### admin_activity_logs
```sql
CREATE TABLE admin_activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES admin_users(admin_id)
);
```

## 🛠️ Technology Stack

### Backend
- **Flask 3.0** - Web framework
- **Flask-JWT-Extended** - JWT authentication
- **PyMySQL** - MySQL connector
- **bcrypt** - Password hashing
- **Pillow** - CAPTCHA image generation
- **Flask-CORS** - CORS handling

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **React Router v6** - Routing
- **Sonner** - Toast notifications
- **Lucide React** - Icons

### Database
- **MySQL 8.0+** - Database management system

## 📚 Documentation

- [Quick Start Guide](QUICK_START.md) - Get started in 5 minutes
- [Setup Instructions](SETUP_INSTRUCTIONS.md) - Detailed setup guide
- [System Architecture](SYSTEM_ARCHITECTURE.md) - Architecture overview
- [Session Expiry Feature](SESSION_EXPIRY_FEATURE.md) - Session management details
- [Backend README](backend/README.md) - Backend documentation

## 🔧 Configuration

### Backend (.env)
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=moneyone_db
JWT_SECRET_KEY=your-secret-key
FLASK_ENV=development
```

### Frontend (admin_api.js)
```javascript
const API_BASE_URL = 'http://localhost:5000/api/admin';
```

## 🐛 Troubleshooting

### Backend Issues

**Database Connection Error**
```bash
# Check MySQL is running
# Verify credentials in .env
# Ensure database exists
```

**Module Not Found**
```bash
pip install -r requirements.txt
```

### Frontend Issues

**CORS Error**
```bash
# Ensure backend is running
# Check CORS config in app.py
```

**API Connection Failed**
```bash
# Verify backend is on port 5000
# Check API_BASE_URL in admin_api.js
```

## 🚀 Production Deployment

### Backend
1. Change `JWT_SECRET_KEY` to strong random string
2. Set `FLASK_ENV=production`
3. Use production WSGI server (gunicorn)
4. Enable HTTPS
5. Configure proper CORS origins

### Frontend
1. Build: `npm run build`
2. Deploy `dist` folder
3. Update API_BASE_URL to production
4. Enable HTTPS

### Database
1. Change default admin password
2. Set strong MySQL password
3. Enable SSL connections
4. Regular backups
5. Restrict access

## 📈 Future Enhancements

- [ ] Two-factor authentication (2FA)
- [ ] Email notifications
- [ ] Password reset functionality
- [ ] Role-based access control (RBAC)
- [ ] API rate limiting
- [ ] Session management dashboard
- [ ] Advanced activity analytics
- [ ] Export logs to CSV/PDF
- [ ] Real-time notifications
- [ ] Mobile app support

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a pull request

## 📄 License

This project is proprietary software for CraftPay payment gateway.

## 👥 Support

For issues or questions:
- Check documentation files
- Review troubleshooting section
- Check backend logs
- Inspect browser console

## 🔒 Security Features

✅ Production-ready authentication system
✅ Session expiry with user-friendly warnings
✅ Comprehensive security measures
✅ Beautiful, modern UI
✅ Complete activity logging
✅ Easy to deploy and maintain
✅ Well-documented codebase
✅ Scalable architecture

---

**Built with ❤️ for CraftPay Payment Gateway**
