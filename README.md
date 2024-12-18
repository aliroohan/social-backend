# FastAPI Social Network API

This is a FastAPI application that serves as a backend for a social networking platform. It provides endpoints for user management, friendship management, and post management.

## Features

- User registration and authentication
- Create, read, update, and delete posts
- Manage friendships between users
- Retrieve mutual friends and suggested friends
- CORS support for frontend applications

## Requirements

- Python 3.7 or higher
- PostgreSQL database
- FastAPI
- psycopg2
- pydantic
- python-dotenv

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:

   ```bash
   pip install fastapi psycopg2 python-dotenv
   ```

4. Set up your PostgreSQL database and create the necessary tables. You can use the following SQL commands as a reference:

   ```sql
   CREATE TABLE users (
       id SERIAL PRIMARY KEY,
       name VARCHAR(100) NOT NULL,
       email VARCHAR(100) NOT NULL,
       password VARCHAR(100) NOT NULL,
       bio TEXT
   );

   CREATE TABLE posts (
       id SERIAL PRIMARY KEY,
       user_id INT REFERENCES users(id),
       content TEXT NOT NULL,
       time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );

   CREATE TABLE friendship (
       user1_id INT REFERENCES users(id),
       user2_id INT REFERENCES users(id),
       PRIMARY KEY (user1_id, user2_id)
   );
   ```

5. Create a `.env` file in the root directory of the project with the following content:

   ```env
   user=<your_db_user>
   password=<your_db_password>
   host=<your_db_host>
   port=<your_db_port>
   dbname=<your_db_name>
   ```

## Running the Application

To run the FastAPI application, use the following command:

```bash
   uvicorn api:app --reload
   ```


You can access the API documentation at `http://127.0.0.1:8000/docs`.

## API Endpoints

- **User Management**
  - `POST /users/` - Create a new user
  - `GET /users/` - Get all users except the specified user
  - `GET /user/` - Get user data by name and password
  - `POST /bio/` - Edit user bio
  - `GET /bio/` - Get user bio

- **Post Management**
  - `POST /posts/` - Create a new post
  - `GET /posts/` - Get posts by user ID

- **Friendship Management**
  - `POST /friend/{user_id1}/{user_id2}` - Create a friendship
  - `DELETE /friend/{user_id1}/{user_id2}` - Delete a friendship
  - `GET /friends/{user_id}` - Get all friends of a user
  - `GET /mutual-friends/{user_id1}/{user_id2}` - Get mutual friends of two users
  - `GET /suggested-friends/{user_id}` - Get suggested friends for a user

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
