from flask import Flask, request, jsonify
import cv2
import numpy as np
import os
import logging
from pytube import YouTube
import requests
from urllib.error import HTTPError

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

def download_youtube_video(url, filename):
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(file_extension='mp4').first()
        if not stream:
            raise Exception("No valid video stream found.")
        stream.download(filename=filename)
    except HTTPError as e:
        logging.error(f"HTTP Error: {e.code} - {e.reason}")
        raise
    except Exception as e:
        logging.error(f"An error occurred while downloading the video: {str(e)}")
        raise

def download_vimeo_video(url, filename):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception("Failed to download Vimeo video")
        with open(filename, 'wb') as f:
            f.write(response.content)
    except Exception as e:
        logging.error(f"An error occurred while downloading the Vimeo video: {str(e)}")
        raise

def extract_frames(video_path):
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Failed to open video file: {video_path}")
        frames = []
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()
        return frames
    except Exception as e:
        logging.error(f"An error occurred while extracting frames: {str(e)}")
        raise

def load_eye_detector():
    try:
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        return eye_cascade
    except Exception as e:
        logging.error(f"Error loading eye detector model: {str(e)}")
        raise

def detect_and_blur_eyes(eye_cascade, frame):
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray, 1.1, 4)
        for (x, y, w, h) in eyes:
            eye = frame[y:y+h, x:x+w]
            eye = cv2.GaussianBlur(eye, (99, 99), 30)
            frame[y:y+h, x:x+w] = eye
        return frame
    except Exception as e:
        logging.error(f"An error occurred while detecting and blurring eyes: {str(e)}")
        raise

def reassemble_video(frames, output_path, fps=30):
    try:
        height, width, _ = frames[0].shape
        video_out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
        for frame in frames:
            video_out.write(frame)
        video_out.release()
    except Exception as e:
        logging.error(f"An error occurred while reassembling video: {str(e)}")
        raise

@app.route('/blur-eyes', methods=['POST'])
def blur_eyes_in_video():
    try:
        data = request.get_json()
        source_type = data.get('type')
        path_or_url = data.get('path/url')
        output_filename = data.get('output_filename', 'blurred_eyes_video.mp4')
        if not source_type or not path_or_url:
            return jsonify({"error": "No source type or path/URL provided"}), 400

        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)

        video_path = os.path.join(downloads_dir, 'video.mp4')
        output_path = os.path.join(downloads_dir, output_filename)

        if source_type == 'youtube':
            logging.info(f"Downloading YouTube video from URL: {path_or_url}")
            download_youtube_video(path_or_url, video_path)
        elif source_type == 'vimeo':
            logging.info(f"Downloading Vimeo video from URL: {path_or_url}")
            download_vimeo_video(path_or_url, video_path)
        elif source_type == 'local':
            logging.info(f"Using local video file: {path_or_url}")
            if not os.path.exists(path_or_url):
                return jsonify({"error": "Local file not found"}), 400
            video_path = path_or_url
        else:
            return jsonify({"error": "Invalid source type"}), 400

        logging.info("Video downloaded successfully")

        logging.info("Extracting frames from video")
        frames = extract_frames(video_path)
        eye_cascade = load_eye_detector()
        logging.info("Loaded eye detector model")
        logging.info("Detecting and blurring eyes in frames")
        blurred_frames = [detect_and_blur_eyes(eye_cascade, frame) for frame in frames]
        logging.info("Reassembling video from blurred frames")
        reassemble_video(blurred_frames, output_path)

        if source_type in ['youtube', 'vimeo']:
            os.remove(video_path)
        logging.info("Video processed successfully")
        return jsonify({"message": "Video processed successfully", "output_file": output_path}), 200

    except HTTPError as e:
        logging.error(f"HTTP Error: {e.code} - {e.reason}")
        return jsonify({"error": f"HTTP Error: {e.code} - {e.reason}"}), 500
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": f"An internal error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
