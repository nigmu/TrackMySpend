from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def fun1():
    return {"message": "Hello World"}