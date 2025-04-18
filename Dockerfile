# Stage 1: Base Python Image
# Use an official Python runtime as a parent image.
# The '-slim' variant is smaller and good for production.
# Choose a version compatible with your dependencies (e.g., 3.10 or 3.11 often have good compatibility)
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Install essential system dependencies required for building dlib and running opencv-python
# - build-essential: Provides C/C++ compilers (gcc, g++) and make.
# - cmake: Required by dlib for its build process.
# - pkg-config: Often needed to find library details during compilation.
# - libx11-dev: Common dependency for GUI features, sometimes needed even for headless builds.
# - libgl1-mesa-glx, libglib2.0-0: Common runtime dependencies for OpenCV headless operations.
# Add other libraries if specific build errors indicate they are missing.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libx11-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
 # Clean up apt cache to reduce image size
 && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container first
# This leverages Docker's layer caching. If requirements.txt doesn't change,
# Docker won't reinstall dependencies on subsequent builds (unless the layer cache is invalidated).
COPY requirements.txt requirements.txt

# Install Python dependencies specified in requirements.txt
# --no-cache-dir reduces image size by not storing the pip download cache.
# Ensure 'gunicorn', 'Flask', 'opencv-python', 'dlib', 'face_recognition', 'numpy' are in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code (app.py, known_faces/ directory, etc.)
# into the container's working directory (/app).
# Ensure you have a .dockerignore file to exclude unnecessary files (like venv, .git, __pycache__)
COPY . .

# Set a default port environment variable.
# Hosting platforms like Render will typically override this with their own $PORT variable.
ENV PORT=5001

# Expose the port the container will listen on at runtime.
# This uses the PORT environment variable. It's mainly documentation for Docker.
EXPOSE $PORT

# Define the command to run the application using Gunicorn (production WSGI server).
# - "gunicorn": The command to run.
# - "--bind": Specifies the address and port to bind to.
# - "0.0.0.0:$PORT": Binds to all available network interfaces inside the container
#   on the port specified by the $PORT environment variable (provided by Render/Heroku etc.).
# - "app:app": Tells Gunicorn to look for the file 'app.py' (the first 'app')
#   and find the Flask application instance named 'app' inside it (the second 'app').
#   Adjust 'app:app' if your filename or Flask variable name is different.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
