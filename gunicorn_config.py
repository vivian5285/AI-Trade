bind = "127.0.0.1:5001"
workers = 2
timeout = 120
accesslog = "/root/AI-Trade/logs/gunicorn.access.log"
errorlog = "/root/AI-Trade/logs/gunicorn.error.log"
capture_output = True
enable_stdio_inheritance = True 