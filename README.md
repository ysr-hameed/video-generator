# Video Generator - Joker Style Animated Text Video

A Python script that generates animated videos with Joker-style text effects, TTS audio, and synchronized subtitles.

## Features

- Joker-inspired dark theme with neon accent colors (green/purple)
- Animated word-by-word text reveal with multiple animations
- Auto-generated TTS audio using Edge TTS
- VTT subtitle file generation
- Particle effects for visual enhancement
- Word-by-word color cycling

## Requirements

- Python 3.8+
- FFmpeg
- Pillow
- edge-tts

## Installation

```bash
pip install -r requirements.txt
```

## Usage

1. Edit `script.txt` with your desired text content
2. Run the script:

```bash
python main.py
```

3. Output will be in:
   - `output/video.mp4` - Final video
   - `audio/script.mp3` - TTS audio
   - `audio/subtitles.vtt` - Subtitles file

## Configuration

Edit these variables in `main.py`:

- `FPS` - Frames per second (default: 15)
- `WORDS_PER_LINE` - Words per scene (default: 5)
- `JOKER_THEMES` - Color themes for different scenes
- `ANIMATIONS` - List of animation types

## Animations

- `slide_up` - Words slide up into position
- `zoom_in` - Words zoom in
- `bounce` - Words bounce into place
- `fade_in` - Words fade in
- `slide_left` - Words slide from left

## License

MIT
