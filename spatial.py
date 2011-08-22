from pymongo import Connection
import time

connection = Connection('localhost', 27017)
usercollection = connection.geodb.users

def login(user,connection,loc):
    usercollection.insert({"user": user, "time": time.time(), "connection": connection, "loc": loc})

def logout(user,connection):
    usercollection.remove({"user":user,"connection":connection})

def neighbours(user):
    user = usercollection.find_one({"user": user})
    for nearuser in usercollection.find( { "loc" : { "$near" : user[unicode('loc')] } } ).limit(20):
        print (nearuser)

def test():
    user_spatial_login("testuser1",1,[5,5])
    user_spatial_login("testuser2",2,[3,2])
    user_spatial_login("testuser3",3,[7,2])
    user_spatial_login("testuser4",4,[3,5])
    getnearuser("testuser1")
    usercollection.remove()
