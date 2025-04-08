import argparse
import os
import time
import json
import subprocess
import cv2
import numpy as np
import vosk
import wave
import ffmpeg
from tqdm import tqdm

def extract_audio(video_path, audio_path="temp_audio.wav"):
    print(f"Extracting audio from {video_path}...")
    
    try:
        (
            ffmpeg
            .input(video_path)
            .output(audio_path, acodec='pcm_s16le', ac=1, ar='16000')
            .run(quiet=True, overwrite_output=True)
        )
        print("Audio extraction complete")
        return audio_path
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None

def transcribe_audio(audio_path, model_path=None):
    print("Transcribing audio...")
    
    if model_path is None:
        if os.path.exists("model"):
            model_path = "model"
        else:
            print("No model specified. Using small model...")
            from vosk import Model
            model = Model(model_name="vosk-model-small-en-us-0.15")
            model_path = model.model_path
    
    model = vosk.Model(model_path)
    
    wf = wave.open(audio_path, "rb")
    
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        print("Audio file must be WAV format mono PCM.")
        return None
    
    rec = vosk.KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)
    
    results = []
    
    total_frames = wf.getnframes()
    frames_per_chunk = 4000
    total_chunks = total_frames // frames_per_chunk
    
    for i in tqdm(range(0, total_chunks + 1), desc="Transcribing"):
        data = wf.readframes(frames_per_chunk)
        if len(data) == 0:
            break
            
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if 'result' in result:
                results.extend(result['result'])
    
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result:
        results.extend(final_result['result'])
    
    subtitles = convert_to_subtitles(results, wf.getframerate())
    
    wf.close()
    print(f"Transcription complete. Generated {len(subtitles)} subtitle segments.")
    return subtitles

def convert_to_subtitles(word_results, sample_rate, max_chars=60):
    if not word_results:
        return []
    
    subtitles = []
    current_subtitle = {
        "text": "",
        "words": [],
        "start_time": word_results[0]["start"],
        "end_time": word_results[0]["end"]
    }
    
    for word_data in word_results:
        word = word_data["word"]
        
        if len(current_subtitle["text"] + word) > max_chars:
            subtitles.append(current_subtitle)
            current_subtitle = {
                "text": word + " ",
                "words": [word_data],
                "start_time": word_data["start"],
                "end_time": word_data["end"]
            }
        else:
            current_subtitle["text"] += word + " "
            current_subtitle["words"].append(word_data)
            current_subtitle["end_time"] = word_data["end"]
    
    if current_subtitle["text"]:
        subtitles.append(current_subtitle)
    
    for sub in subtitles:
        sub["text"] = sub["text"].strip()
        if sub["text"]:
            sub["text"] = sub["text"][0].upper() + sub["text"][1:]
        if sub["text"] and sub["text"][-1] not in ".!?":
            sub["text"] += "."
    
    return subtitles

def create_subtitled_video(video_path, subtitles, output_path):
    print("Adding subtitles to video...")
    
    temp_video_path = "temp_subtitled_video.mp4"
    
    cap = cv2.VideoCapture(video_path)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))
    
    frame_idx = 0
    subtitle_idx = 0
    active_subtitle = None
    
    with tqdm(total=total_frames, desc="Processing frames") as pbar:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            current_time = frame_idx / fps
            
            while subtitle_idx < len(subtitles) and current_time >= subtitles[subtitle_idx]["end_time"]:
                subtitle_idx += 1
            
            if subtitle_idx < len(subtitles) and current_time >= subtitles[subtitle_idx]["start_time"]:
                active_subtitle = subtitles[subtitle_idx]
            else:
                active_subtitle = None
            
            if active_subtitle:
                frame = add_subtitle_to_frame(frame, active_subtitle["text"])
            
            out.write(frame)
            
            frame_idx += 1
            pbar.update(1)
    
    cap.release()
    out.release()
    
    print("Merging video with original audio...")
    
    try:
        input_video = ffmpeg.input(temp_video_path)
        input_audio = ffmpeg.input(video_path).audio
        
        ffmpeg.output(
            input_video, 
            input_audio, 
            output_path, 
            vcodec='copy',
            acodec='aac'
        ).run(quiet=True, overwrite_output=True)
        
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        print(f"Video with subtitles and audio saved to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error merging audio: {e}")
        
        if os.path.exists(temp_video_path):
            print("Returning video without audio")
            os.rename(temp_video_path, output_path)
            return output_path
        return None

def add_subtitle_to_frame(frame, text):
    height, width = frame.shape[:2]
    
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.7
    thickness = 1
    text_color = (255, 255, 255)
    outline_color = (0, 0, 0)
    
    max_width = width - 100
    lines = wrap_text(text, font, font_scale, thickness, max_width)
    
    line_height = 30
    total_height = len(lines) * line_height
    
    y_position = height - 50 - total_height
    
    for i, line in enumerate(lines):
        y = y_position + i * line_height
        
        (text_width, text_height), _ = cv2.getTextSize(line, font, font_scale, thickness)
        
        x = (width - text_width) // 2
        
        bg_padding = 10
        overlay = frame.copy()
        cv2.rectangle(
            overlay, 
            (x - bg_padding, y - text_height - bg_padding),
            (x + text_width + bg_padding, y + bg_padding),
            (0, 0, 0), 
            -1
        )
        alpha = 0.6
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            cv2.putText(frame, line, (x + dx, y + dy), font, font_scale, outline_color, thickness, cv2.LINE_AA)
        
        cv2.putText(frame, line, (x, y), font, font_scale, text_color, thickness, cv2.LINE_AA)
    
    return frame

def wrap_text(text, font, font_scale, thickness, max_width):
    words = text.split()
    if not words:
        return []
        
    lines = []
    current_line = []
    
    for word in words:
        test_line = current_line + [word]
        test_text = ' '.join(test_line)
        
        (text_width, _), _ = cv2.getTextSize(test_text, font, font_scale, thickness)
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def clean_up_temp_files(temp_files):
    for file_path in temp_files:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Removed temporary file: {file_path}")
            except Exception as e:
                print(f"Failed to remove temporary file {file_path}: {e}")
                
    for temp_file in ["temp_subtitled_video.mp4", "temp_audio.wav"]:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                print(f"Removed temporary file: {temp_file}")
            except Exception as e:
                print(f"Failed to remove temporary file {temp_file}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Generate subtitles for a video")
    parser.add_argument("input", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Path to output video file (default: input_subtitled.mp4)")
    parser.add_argument("-m", "--model", help="Path to Vosk model directory")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary files")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist")
        return
    
    if not args.output:
        base_name = os.path.splitext(args.input)[0]
        args.output = f"{base_name}_subtitled.mp4"
    
    print(f"Input video: {args.input}")
    print(f"Output will be saved to: {args.output}")
    
    start_time = time.time()
    temp_files = []
    
    try:
        audio_path = extract_audio(args.input)
        temp_files.append(audio_path)
        
        if not audio_path:
            print("Failed to extract audio. Exiting.")
            return
        
        subtitles = transcribe_audio(audio_path, args.model)
        
        if not subtitles:
            print("No speech detected or transcription failed. Exiting.")
            return
        
        output_video = create_subtitled_video(args.input, subtitles, args.output)
        
        if not output_video:
            print("Failed to create output video. Exiting.")
            return
        
        elapsed_time = time.time() - start_time
        mins, secs = divmod(int(elapsed_time), 60)
        print(f"Process completed in {mins} minutes and {secs} seconds")
        print(f"Video with subtitles and audio saved to: {args.output}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if not args.keep_temp:
            clean_up_temp_files(temp_files)
        else:
            print("Temporary files were kept as requested")

if __name__ == "__main__":
    main()