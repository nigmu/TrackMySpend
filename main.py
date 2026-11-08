import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.app:app", host="0.0.0.0", port=2006, reload=True, access_log=False)
