# Poker Ledger

Poker Ledger is a full-stack web application designed to track poker sessions, visualize financial performance, and promote responsible gambling habits through personal loss-limit alerts.

The application helps users understand their spending patterns and recognize when losses may be becoming excessive.

## Screenshots

### Dashboard

The dashboard provides an overview of session history, profits and losses, performance charts, and personal loss-limit monitoring.

![Poker Ledger Dashboard](docs/p-dashboard.png)

### Login Page

Users can securely sign in to access their personal session records and financial tracking dashboard.

![Poker Ledger Login](docs/login.png)

## Features

- **Session Tracking:** Add, edit, and delete poker sessions while recording profits and losses.
- **Performance Analytics:** Visualize financial performance and review historical session data.
- **Responsible Gambling Alerts:** Set personal loss thresholds and receive warnings when losses reach those limits. These alerts are intended to discourage excessive gambling and encourage users to reassess their spending.
- **Leaderboards:** View recorded results across different time periods.
- **User Authentication:** Secure account registration and login with password hashing.
- **Admin Dashboard:** Role-restricted administrative tools for managing accounts and session records.

## Tech Stack

**Backend:** Python, Flask, SQLAlchemy

**Frontend:** HTML, CSS, JavaScript

**Database:** SQLite

**Authentication & Security:** Flask-Login, Argon2 password hashing, CSRF protection, rate limiting

**Deployment:** AWS EC2, Gunicorn, Nginx, HTTPS

## Project Purpose

Poker Ledger was developed as a practical full-stack application combining web development, database management, authentication, and data visualization.

A central focus is **responsible gambling awareness**. Rather than encouraging additional gambling, the application's loss-limit alerts help users identify potentially harmful spending patterns and make more informed decisions about when to stop playing.

The project also demonstrates experience with backend development, access controls, secure authentication, and deploying a production web application.

## Disclaimer

Poker Ledger is intended for personal financial tracking and awareness. It does not facilitate gambling, guarantee financial outcomes, or replace professional support for gambling-related problems.
