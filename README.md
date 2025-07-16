# Product-price-tracker

This project allows users to track the price of products from websites like Amazon and receive alerts when prices drop below their desired value. 
It is built using Python, Flask, SQLite, and BeautifulSoup. Postman is used to test the API endpoints.

#Features

- User registration with email and alert preferences
- Product tracking by URL and target price
- Periodic price checking (every 30 minutes)
- Email notifications when the current price falls below the target price
- API endpoints tested using Postman
- Optional Redis caching for performance optimization

# Tech Stack

- Python 
- Flask (Web framework)
- SQLite (Relational database)
- BeautifulSoup (HTML scraping)
- Redis (optional caching)
- Schedule + Threading (background tasks)
- Dotenv (environment variable management)
- Postman (API testing)
- smtplib (email sending)

# API Endpoints
##1. Register User

*POST* /api/users
Request Body from postman
json(format)
