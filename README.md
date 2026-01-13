# SimLeagues 🏁

A comprehensive platform for managing sim racing leagues and championships across multiple racing simulators.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Django](https://img.shields.io/badge/django-5.0+-green.svg)](https://www.djangoproject.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 📋 Overview

SimLeagues is an open-source platform designed to help sim racing communities organize and manage their leagues, championships, and races. Starting with Le Mans Ultimate support, with plans to extend to iRacing, Gran Turismo 7, and other racing simulators.

### Key Features

- 🏆 **League Management**: Create and manage racing leagues with customizable settings
- 📅 **Championship Organization**: Run multiple championships within a league
- 🏁 **Race Tracking**: Record and manage race results with detailed statistics
- 👥 **User Roles**: Admin and member roles with appropriate permissions
- 📊 **Standings & Statistics**: Automatic calculation of championship standings
- 🎮 **Multi-Game Support**: Designed to support multiple racing simulators (starting with Le Mans Ultimate)

## 🚀 Tech Stack

**Backend:**
- Django 5.0+
- Django REST Framework
- PostgreSQL
- Python 3.11+

**Frontend** (separate repository):
- React 18+
- TypeScript
- TanStack Query
- Tailwind CSS

## 🛠️ Installation

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+
- pip and virtualenv

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/flodell/simleagues-backend.git
cd simleagues-backend
```

2. **Create and activate virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database setup**
```bash
# Create PostgreSQL database
createdb simleagues_db

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

6. **Run development server**
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## 📁 Project Structure
```
simleagues-backend/
├── simleagues/           # Project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── cars/            # Car models and management
│   ├── tracks/          # Track/circuit management
│   ├── leagues/         # League and membership
│   ├── championships/   # Championship management
│   ├── races/          # Race and results
│   └── users/          # User authentication
├── docs/               # Documentation
├── requirements.txt
└── README.md
```

## 🎯 Roadmap

### Phase 1: MVP (Current)
- [x] Project setup and architecture
- [ ] Core models (Car, Track, League, Championship, Race)
- [ ] Django admin interface for data entry
- [ ] Basic REST API endpoints
- [ ] User authentication and permissions

### Phase 2: Core Features
- [ ] Championship standings calculation
- [ ] Race result management by league admins
- [ ] Public league pages
- [ ] Driver statistics

### Phase 3: Enhanced Features
- [ ] Multiple point systems support
- [ ] Team championships
- [ ] Advanced statistics and analytics
- [ ] Export functionality (PDF, CSV)

### Phase 4: Multi-Game Support
- [ ] iRacing integration
- [ ] Gran Turismo 7 support
- [ ] Additional simulators

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](https://github.com/flodell/simleagues-backend/CONTRIBUTING.md) for details on our code of conduct and development process.

## 📝 API Documentation

API documentation will be available at `/api/docs/` when running the development server.

## 🧪 Testing
```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=apps

# Run linting
black .
flake8 .
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/flodell/simleagues-backend/LICENSE) file for details.

## 👨‍💻 Author

**Flo** - [@flodell](https://github.com/flodell)

## 🙏 Acknowledgments

- Built with [Django](https://www.djangoproject.com/)
- Inspired by the sim racing community
- Special thanks to all contributors

## 📞 Support

If you have any questions or need help, please:
- Open an issue on [GitHub Issues](https://github.com/flodell/simleagues-backend/issues)
- Join our [Discord community](#) (coming soon)

---

**Note**: This project is in active development. Features and documentation are subject to change.