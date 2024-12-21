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
    mutualCount:int = 0
    bio: str = ""

class Comment(BaseModel):
    name: str = ""
    comment: str = "" 

class Post(BaseModel):
    id: int  
    user_id: int
    user_name: str = ""
    content:str = ""
    time:str = ""
    likesCount:int = 0
    likes: List[str] = []
    commentCount:int = 0
    comments: List[Comment] = []

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
       "https://connevo.vercel.app",
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
            id, name = user
            graph[id] = set()

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

load_data()
print(graph.keys())

def get_mutual_count(user_id1: int, user_id2: int) -> int:
    load_data()
    mutuals = [friend for friend in graph[user_id1] if friend in graph[user_id2]]
    return len(mutuals)

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
    

# not using
@app.get("/posts/", response_model=List[Post])
async def get_posts(user_id: int) -> List[Post]:
    load_data()
    
    try:
        cursor.execute("SELECT id,content,likes_count FROM posts WHERE user_id = %s", (user_id,))
        posts = cursor.fetchall()
        result = [Post(id=post[0],user_id=user_id, user_name=users[user_id], content=post[1], likescount=post[2]) for post in posts]
        for post in result:
            cursor.execute("SELECT user_id FROM likes WHERE post_id = %s", (post.id,))
            likes = cursor.fetchall()
            post.likes = [users[like[0]] for like in likes]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# get all posts of friends
# called at 1st page load
@app.post("/post/")
async def get_post(user_ids: List[int]) -> List[Post]:
    load_data()
    try:
        posts = []
        user_ids_tuple = tuple(user_ids)
        
        # Use IN clause to get all posts for the given user_ids
        cursor.execute("SELECT id, user_id, content, time, likes_count,comment_count FROM posts WHERE user_id IN %s ORDER BY time,id ASC", (user_ids_tuple,))
        fetched_posts = cursor.fetchall()
        
        for id, user_id, content, time, likes_count, comment_count in fetched_posts:
            post = Post(id=id, user_id=user_id, user_name=users[user_id], content=content, time=str(time), likesCount=likes_count, commentCount=comment_count)
            cursor.execute("SELECT user_id FROM likes WHERE post_id = %s", (post.id,))
            likes = cursor.fetchall()
            post.likes = [users[like[0]] for like in likes]
            cursor.execute("SELECT user_id, comment FROM comments WHERE post_id = %s", (post.id,))
            comments = cursor.fetchall()
            post.comments = [Comment(name=users[comment[0]], comment=comment[1]) for comment in comments]
            posts.append(post)
        
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# get all friends of a user
# called at my friends page
@app.get("/friends/{user_id}", response_model=List[User])
async def get_friends(user_id: int) -> List[User]:
    load_data()
    try:
        list1 = []
        for friend in list(graph[user_id]):
            list1.append(User(id=friend, name=users[friend], password="",mutualCount=get_mutual_count(friend,user_id)))
        
        if len(list1) == 0:
            raise HTTPException(status_code=404, detail="User has no friends")
        return list1
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# get all mutual friends of two users
# called at mutual friends page
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


# get all suggested friends of a user
# called at suggested friends page
@app.get("/suggested-friends/{user_id}")
async def get_suggested_friends(user_id: int) -> List[User]:
    load_data()
    try:
        suggestions = set()
        for friend in graph[user_id]:
            for friend_of_friend in graph[friend]:
                if friend_of_friend != user_id and friend_of_friend not in graph[user_id]:
                    suggestions.add(friend_of_friend)
        suggest = [User(id=friend,name=users[friend],mutualCount=get_mutual_count(friend,user_id)) for friend in list(suggestions)]
        return suggest
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Create a new user
# called at sign up
@app.post("/users/")
async def create_user(name: str, email: str, password: str) -> Dict:
    load_data()
    
    if name in ids.keys():
        raise HTTPException(status_code=400, detail="User already exists")
    try:
        cursor.execute("INSERT INTO users (name, email, password,bio) VALUES (%s, %s, %s, " + "'Hi, I am " + name + "')", (name, email, password))
        db.commit()
        load_data()
        return {"message": f"User '{name}' added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# Get all users except the user with the given id
# called in add friend page
@app.get("/users/")
async def get_users(id: int) -> List[User]:
    load_data()
    try:
        cursor.execute("SELECT id, name, bio FROM users")
        users_data = cursor.fetchall()
        return [User(id=user[0], name=user[1],email="", password="",mutualCount=get_mutual_count(user[0],id), bio=user[2]) for user in users_data if user[0] != id]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# add bio
# called when bio is edited
@app.post("/bio/")
async def edit_bio(user_id: int, bio: str) -> Dict:
    load_data()
    
    try:
        cursor.execute("UPDATE users SET bio = %s WHERE id = %s", (bio, user_id))
        db.commit()
        return {"message": "Bio added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/bio/")
async def get_bio(user_id: int) -> Dict:
    load_data()
    
    try:
        cursor.execute("SELECT bio FROM users WHERE id = %s", (user_id,))
        bio = cursor.fetchone()
        if bio is None:
            raise HTTPException(status_code=404, detail="Bio not found")
        return {"bio": bio[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")   

# get user data
# called at login
@app.get("/user/")
async def get_user(name: str, password: str):
    load_data()
    
    if name not in ids.keys():
        raise HTTPException(status_code=404, detail="User not found")
    else:
        try:
            cursor.execute("SELECT id, name, email, password, bio FROM users WHERE name = %s", (name,))
            user_data = cursor.fetchone()

            if user_data is None:
                raise HTTPException(status_code=404, detail="User not found")

            passcode = user_data[3]
            user = User(id=user_data[0], name=user_data[1], email=user_data[2], password=user_data[3],mutualCount=get_mutual_count(ids[name],user_data[0]), bio=user_data[4])

            if passcode == password:
                return user
            else:   
                raise HTTPException(status_code=400, detail="Password is incorrect")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# create post
# called at create post page
@app.post("/posts/")
async def create_post(user_id: int, content: str) -> Dict:
    load_data()

    try:
        cursor.execute("INSERT INTO posts (user_id, content) VALUES (%s, %s)", (user_id, content))
        db.commit()
        return {"message": "Post added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# called at add friend button
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
        cursor.execute("INSERT INTO friendship (user1_id, user2_id) VALUES (%s, %s)", (user_id1, user_id2))
        cursor.execute("INSERT INTO friendship (user1_id, user2_id) VALUES (%s, %s)", (user_id2, user_id1))
        db.commit()
        return {"message": f"Friendship created between {user_id1} and {user_id2}"}
    except HTTPException:
        raise HTTPException(status_code=400, detail="Friendship already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# called at remove friend button
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
        cursor.execute("DELETE FROM friendship WHERE user1_id = %s AND user2_id = %s", (user_id1, user_id2))
        cursor.execute("DELETE FROM friendship WHERE user1_id = %s AND user2_id = %s", (user_id2, user_id1))
        db.commit()
        return {"message": f"Friendship between {user_id1} and {user_id2} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/like/{user_id}/{post_id}")
async def like_post(user_id: int, post_id: int) -> Dict:
    load_data()
    
    try:
        cursor.execute("SELECT user_id FROM likes WHERE post_id = %s", (post_id,))
        likes = cursor.fetchall()
        if (user_id,) in likes:
            raise HTTPException(status_code=400, detail="Post already liked")

        cursor.execute("INSERT INTO likes (user_id, post_id) VALUES (%s, %s)", (user_id, post_id))
        db.commit()
        return {"message": "Post liked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/like/{user_id}/{post_id}")
async def unlike_post(user_id: int, post_id: int) -> Dict:
    load_data()
    
    try:
        cursor.execute("SELECT user_id FROM likes WHERE post_id = %s", (post_id,))
        likes = cursor.fetchall()
        if (user_id,) not in likes:
            raise HTTPException(status_code=400, detail="Post not liked")

        cursor.execute("DELETE FROM likes WHERE user_id = %s AND post_id = %s", (user_id, post_id))
        db.commit()
        return {"message": "Post unliked successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))