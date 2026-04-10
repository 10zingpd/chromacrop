# chromacrop

A Viam camera module that dynamically crops a camera feed to a color-detected border region. Point it at any colored tape, border, or marker and it crops the frame to just that region.

## Configuration

Add this module as a camera component. Required and optional attributes:

| Attribute | Type | Required | Default | Description |
|---|---|---|---|---|
| `source` | string | yes | — | Name of the upstream camera to read from |
| `detect_color` | string | yes | — | Hex color to detect (e.g. `"#dcfe79"` for lime green) |
| `hue_tolerance_pct` | float | no | `0.05` | How much hue variation to allow (0.0–1.0, percentage of hue wheel) |
| `segment_size_px` | int | no | `100` | Minimum contour area in pixels (filters noise) |
| `padding` | int | no | `5` | Extra pixels around the detected region |

### Example config

```json
{
  "source": "my-webcam",
  "detect_color": "#dcfe79",
  "hue_tolerance_pct": 0.05,
  "segment_size_px": 100,
  "padding": 5
}
```

## How it works

1. Reads a frame from the source camera
2. Converts the target hex color to HSV and builds a detection range
3. Thresholds the frame for that color, finds contours
4. Crops to the bounding box of the largest contour (the colored border)
5. Returns the cropped frame as a JPEG

If no matching color is detected, the full uncropped frame is returned as a fallback.

## Requirements

- `viam-sdk`
- `opencv-python-headless`
- `Pillow`
- `numpy`
