import flask
import face_recognition
import numpy as np
import cv2 # OpenCV for image decoding
import base64
import os
import io # For handling image bytes

# --- Configuration ---
KNOWN_FACES_DIR = 'known_faces'
# Lower tolerance means stricter matching (0.6 is typical)
RECOGNITION_TOLERANCE = 0.55
# Use 'hog' for CPU (faster, less accurate) or 'cnn' for GPU (slower, more accurate, needs dlib compiled with CUDA)
DETECTION_MODEL = 'hog'

# --- Load Known Faces ---
print("Loading known faces...")
known_face_encodings = []
known_face_names = []

for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        try:
            # Extract name from filename (remove extension)
            name = os.path.splitext(filename)[0]
            image_path = os.path.join(KNOWN_FACES_DIR, filename)
            
            # Load image using face_recognition
            known_image = face_recognition.load_image_file(image_path)
            
            # Get face encodings. Assume only one face per known image.
            # If multiple faces, use face_encodings(known_image)[0] - but better to ensure single face images.
            encodings = face_recognition.face_encodings(known_image)
            
            if encodings:
                known_face_encodings.append(encodings[0])
                known_face_names.append(name)
                print(f"- Loaded encoding for {name}")
            else:
                print(f"- WARNING: No face found in {filename}. Skipping.")
                
        except Exception as e:
            print(f"- ERROR loading {filename}: {e}")

print(f"Loaded {len(known_face_names)} known face encodings.")


# --- Flask Application ---
app = flask.Flask(__name__)

@app.route('/recognize', methods=['POST'])
def recognize_face_endpoint():
    """
    Receives a base64 encoded image string in JSON payload {'imageData': '...'}
    Returns JSON with recognized name or 'Unknown'.
    """
    response_data = {'recognized': False, 'name': 'Unknown', 'error': None}
    
    if not flask.request.is_json:
        response_data['error'] = "Request must be JSON"
        return flask.jsonify(response_data), 400

    request_json = flask.request.get_json()

    if 'imageData' not in request_json:
        response_data['error'] = "Missing 'imageData' key in JSON payload"
        return flask.jsonify(response_data), 400

    base64_image_data = request_json['imageData']

    try:
        # --- Decode Base64 Image ---
        # Add padding if necessary (Base64 strings should have length multiple of 4)
        missing_padding = len(base64_image_data) % 4
        if missing_padding:
            base64_image_data += '=' * (4 - missing_padding)
            
        image_bytes = base64.b64decode(base64_image_data)
        
        # Convert bytes to numpy array for OpenCV
        np_arr = np.frombuffer(image_bytes, np.uint8)
        
        # Decode image using OpenCV (handles various formats)
        # Use cv2.IMREAD_COLOR to ensure 3 channels (needed by face_recognition)
        img_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img_np is None:
             raise ValueError("Could not decode image data. Is it a valid image format?")

        # Convert from BGR (OpenCV default) to RGB (face_recognition uses)
        rgb_frame = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

        # --- Perform Face Recognition ---
        # Find face locations in the current frame
        face_locations = face_recognition.face_locations(rgb_frame, model=DETECTION_MODEL)
        # Get face encodings for faces found in the current frame
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        recognized_name = "Unknown" # Default

        # Loop through each face found in the frame
        for face_encoding in face_encodings:
            # See if the face is a match for the known face(s)
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=RECOGNITION_TOLERANCE)
            
            # Use the known face with the smallest distance to the new face
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
            
            if len(face_distances) > 0: # Check if there are known faces to compare against
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index]:
                    recognized_name = known_face_names[best_match_index]
                    break # Found a match, stop checking this frame's faces

        # --- Prepare Response ---
        if recognized_name != "Unknown":
            response_data['recognized'] = True
            response_data['name'] = recognized_name
        else:
            response_data['recognized'] = False
            response_data['name'] = "Unknown"

        return flask.jsonify(response_data), 200

    except ValueError as ve:
        print(f"Value Error: {ve}")
        response_data['error'] = f"Image processing error: {ve}"
        return flask.jsonify(response_data), 400
    except Exception as e:
        print(f"An error occurred: {e}")
        response_data['error'] = f"Internal server error: {e}"
        return flask.jsonify(response_data), 500

# --- Health Check Endpoint (Good Practice) ---
@app.route('/health', methods=['GET'])
def health_check():
    return flask.jsonify({'status': 'ok', 'known_faces_loaded': len(known_face_names)}), 200

# --- Run the App ---
if __name__ == '__main__':
    # Host='0.0.0.0' makes it accessible on your network
    # Change port if needed
    app.run(host='0.0.0.0', port=5001, debug=False) # Turn debug=False for production