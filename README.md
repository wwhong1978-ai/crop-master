# crop-master

A cross-platform image cropping tool built with Python and PyQt5. Easily crop images to custom sizes with an intuitive visual interface.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## Features

- **Visual Crop Selection** - Drag to position the crop area, scroll to resize
- **Batch Processing** - Crop multiple images at once with center positioning
- **Customizable Size** - Set custom width and height in pixels
- **Adjustable Crop Box** - 10% to 100% of image size
- **Thumbnail Preview** - Easy navigation through image folders
- **Config Persistence** - Settings auto-save between sessions

## Downloads

Download pre-built executables from the [Releases](https://github.com/wwhong1978-ai/crop-master/releases) page:

- **Windows**: `crop-master.exe`
- **macOS**: `crop-master` (app bundle)
- **Linux**: `crop-master` (executable)

## Installation

### From Release (Recommended)
1. Download the appropriate version for your OS from [Releases](https://github.com/wwhong1978-ai/crop-master/releases)
2. Run the executable

### From Source
```bash
# Clone the repository
git clone https://github.com/wwhong1978-ai/crop-master.git
cd crop-master

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Build from Source
```bash
# Install PyInstaller
pip install pyinstaller

# Build for your platform
pyinstaller --onefile --windowed --name "crop-master" main.py
```

The built executable will be in the `dist/` folder.

## Requirements

- Python 3.10+
- Pillow >= 9.0.0
- PyQt5 >= 5.15.0

## Usage

1. Click **"Open Folder"** to select an image directory
2. Set crop dimensions (width/height in pixels)
3. Adjust the crop box:
   - **Drag** inside the box to move
   - **Scroll wheel** to resize
   - **Right-click** to crop immediately
4. Select output directory
5. Click **"Crop Single"** or **"Batch Crop"**

## Project Structure

```
crop-master/
├── main.py              # Main application entry
├── config.py            # Configuration management
├── image_processor.py   # Image processing logic
├── thumbnail_cache.py   # Thumbnail caching
├── requirements.txt     # Python dependencies
└── 使用说明.md           # Chinese documentation
```

## License

MIT License

---

For Chinese documentation, see [使用说明.md](使用说明.md)
