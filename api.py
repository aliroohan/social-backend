from fastapi import FastAPI, HTTPException
from typing import List, Dict
import psycopg2
from dotenv import load_dotenv
from collections import defaultdict
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI()

class User(BaseModel):
    id: int
    name: str = ""
    email: str = ""
    password: str = ""

class Post(BaseModel):   
    user_id: int
    user_name: str = ""
    content:str = "";

load_dotenv()

db = None
cursor = None
try:
    db = psycopg2.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            port=os.getenv("port"),
            dbname=os.getenv("dbname")
        )
    cursor = db.cursor()
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

graph = defaultdict(set)
users = {}
ids = {}

origins = [
       "https://social-frontend-tau.vercel.app",
        "http://localhost:4200",
   ]

app.add_middleware(
       CORSMiddleware,
       allow_origins=origins,
       allow_credentials=True,
       allow_methods=["*"],  # Allows all methods (GET, POST, OPTIONS, etc.)
       allow_headers=["*"],  # Allows all headers
   )

@app.on_event("startup")
async def startup_event():
    load_data()



def load_data():
    try:
        cursor.execute("SELECT id, name FROM users")
        users_data = cursor.fetchall()
        for user in users_data:
            graph[user[0]] = set()

        cursor.execute("SELECT user1_id, user2_id FROM friendship")
        friendships = cursor.fetchall()
        for friend_pair in friendships:
            user1, user2 = friend_pair
            graph[user1].add(user2)
            graph[user2].add(user1)
        
        cursor.execute("SELECT id, name FROM users")
        users_data = cursor.fetchall()
        for user in users_data:
            id, name = user
            users[id] = name
            ids[name] = id

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/")
def read_root():
    global db, cursor
    try:
        db = psycopg2.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            port=os.getenv("port"),
            dbname=os.getenv("dbname")
        )
        cursor = db.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        load_data()
        return {"db_version": version}
    except Exception as e:
        return {"error": str(e)}
    


@app.get("/posts/", response_model=List[Post])
async def get_posts(user_id: int) -> List[Post]:
    load_data()
    
    try:
        cursor.execute("SELECT content FROM posts WHERE user_id = %s", (user_id,))
        posts = cursor.fetchall()
        return [Post(user_id=user_id, user_name=users[user_id], content=post[0]) for post in posts]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/friends/{user_id}", response_model=List[User])
async def get_friends(user_id: int) -> List[User]:
    load_data()
    try:
        list1 = []
        if user_id not in graph:
            raise HTTPException(status_code=404, detail="User not found")
        for friend in list(graph[user_id]):
            list1.append(User(id=friend, name=users[friend]))
        
        return list1
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mutual-friends/{user_id1}/{user_id2}")
async def get_mutual_friends(user_id1: int, user_id2: int) -> List[User]:
    load_data()
    try:
        if user_id1 not in graph or user_id2 not in graph:
            raise HTTPException(status_code=404, detail="One or both users not found")
        
        mutuals = [friend for friend in graph[user_id1] if friend in graph[user_id2]]
        return [User(id=friend,name=users[friend]) for friend in mutuals]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/suggested-friends/{user_id}")
async def get_suggested_friends(user_id: int) -> List[int]:
    load_data()
    try:
        if user_id not in graph:
            raise HTTPException(status_code=404, detail="User not found")

        suggestions = set()
        for friend in graph[user_id]:
            for friend_of_friend in graph[friend]:
                if friend_of_friend != user_id and friend_of_friend not in graph[user_id]:
                    suggestions.add(friend_of_friend)
        suggest = [users[friend] for friend in list(suggestions)]
        return suggest
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/users/")
async def create_user(name: str, email: str, password: str) -> Dict:
    load_data()
    
    if name in ids.keys():
        raise HTTPException(status_code=400, detail="User already exists")
    try:
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                      (name, email, password))
        db.commit()
        load_data()
        return {"message": f"User '{name}' added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/user/")
async def get_user(name: str, password: str):
    load_data()
    
    if name not in ids.keys():
        raise HTTPException(status_code=404, detail="User not found")
    else:
        try:
            cursor.execute("SELECT id, name, email, password FROM users WHERE name = %s", (name,))
            user_data = cursor.fetchone()

            if user_data is None:
                raise HTTPException(status_code=404, detail="User not found")

            passcode = user_data[3]
            user = User(id=user_data[0], name=user_data[1], email=user_data[2], password=user_data[3])

            if passcode == password:
                return user
            else:   
                raise HTTPException(status_code=400, detail="Password is incorrect")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/posts/")
async def create_post(user_id: int, content: str) -> Dict:
    load_data()
    
    try:
        cursor.execute("INSERT INTO posts (user_id, content) VALUES (%s, %s)", (user_id, content))
        db.commit()
        return {"message": "Post added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/friend/{user_id1}/{user_id2}")
async def create_friendship(user_id1: int, user_id2: int) -> Dict:
    load_data()
    
    try:
        if user_id1 == user_id2:
            raise HTTPException(status_code=400, detail="Users cannot be friends with themselves")

        if user_id1 not in graph or user_id2 not in graph:
            raise HTTPException(status_code=404, detail="One or both users not found")

        if user_id2 in graph[user_id1]:
            raise HTTPException(status_code=400, detail="Friendship already exists")

        graph[user_id1].add(user_id2)
        graph[user_id2].add(user_id1)
        cursor.execute("INSERT INTO friendships (user1_id, user2_id1) VALUES (%s, %s)", (user_id1, user_id2))
        cursor.execute("INSERT INTO friendships (user1_id, user2_id1) VALUES (%s, %s)", (user_id2, user_id1))
        db.commit()
        return {"message": f"Friendship created between {user_id1} and {user_id2}"}
    except HTTPException:
        raise HTTPException(status_code=400, detail="Friendship already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/friend/{user_id1}/{user_id2}")
async def delete_friendship(user_id1: int, user_id2: int) -> Dict:
    load_data()
    
    try:
        if user_id1 not in graph or user_id2 not in graph:
            raise HTTPException(status_code=404, detail="One or both users not found")

        if user_id2 not in graph[user_id1]:
            raise HTTPException(status_code=400, detail="Friendship does not exist")

        graph[user_id1].remove(user_id2)
        graph[user_id2].remove(user_id1)
        cursor.execute("DELETE FROM friendships WHERE user1_id = %s AND user2_id = %s", (user_id1, user_id2))
        cursor.execute("DELETE FROM friendships WHERE user1_id = %s AND user2_id = %s", (user_id2, user_id1))
        db.commit()
        return {"message": f"Friendship between {user_id1} and {user_id2} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))