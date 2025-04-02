this is a public repo the actual one i wrote is in private, it's all messy, that's why i had to create a new one all the features, i implemented in that will be implemented in these aswell, by will implement slowly, like once in a week or 2 weeks

happy coding :>

# Smart Subtitle Generator

A Python tool that automatically adds subtitles to videos by transcribing speech to text and embedding the resulting subtitles directly into the video.

## Features

- Extracts audio from input video
- Transcribes speech to text using Vosk speech recognition
- Generates subtitles with precise timing
- Burns subtitles into the video with clean formatting
- Preserves the original audio in the output
- Zero-delay subtitle display - words appear exactly when they're spoken
- Semi-transparent background for better subtitle readability
- Properly formats text with capitalization and punctuation
- Multi-line subtitle support with word wrapping

## Requirements

- Python 3.6+
- Required Python packages:
  - ffmpeg-python
  - opencv-python (cv2)
  - vosk
  - numpy
  - tqdm
- FFmpeg installed on your system and available in PATH

## Installation

1. Clone or download this repository:
   ```
   git clone https://github.com/yourusername/smart-subtitle-generator.git
   cd smart-subtitle-generator
   ```

2. Install the required packages:
   ```
   pip install ffmpeg-python opencv-python vosk numpy tqdm
   ```

3. Install FFmpeg:
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` or equivalent for your distribution

4. Download a Vosk model:
   - Small models work well and are faster: https://alphacephei.com/vosk/models
   - Extract the model to a folder named "model" in the same directory as the script
   - Alternatively, the script will download a small English model if none is provided

## Usage

Basic usage:

```
python subtitle_generator.py input_video.mp4
```

This will create a file called `input_video_subtitled.mp4` with embedded subtitles.

### Advanced Options

```
python subtitle_generator.py input_video.mp4 -o output_video.mp4 -m /path/to/vosk/model --keep-temp
```

Parameters:
- `input`: Path to the input video file
- `-o, --output`: Path to the output video file (default: input_subtitled.mp4)
- `-m, --model`: Path to Vosk model directory
- `--keep-temp`: Keep temporary files (useful for debugging)

## How It Works

1. **Audio Extraction**: The program extracts the audio track from the video into a temporary WAV file.

2. **Speech Recognition**: Using Vosk, the program transcribes the speech in the audio to text with timestamps for each word.

3. **Subtitle Generation**: Words are grouped into subtitle segments with proper formatting and timing.

4. **Video Processing**: The program creates a new video with the subtitles rendered on each frame at the correct time.

5. **Audio Merging**: The original audio is merged back with the subtitled video to produce the final output.

## Customization

You can modify the code to customize:
- Subtitle appearance (font, size, color, background opacity)
- Maximum characters per subtitle
- Subtitle positioning
- Text formatting rules

## Troubleshooting

- **FFmpeg errors**: Ensure FFmpeg is properly installed and accessible in your PATH
- **Video without audio**: Check if the input video has an audio track
- **Poor transcription quality**: Try using a different/larger Vosk model
- **Memory issues with large videos**: Process the video in smaller segments

## License

This software is provided under the MIT License. Feel free to modify and distribute as needed.

## Acknowledgments

- [Vosk](https://alphacephei.com/vosk/) for the speech recognition engine
- [OpenCV](https://opencv.org/) for video processing
- [FFmpeg](https://ffmpeg.org/) for audio extraction and video merging