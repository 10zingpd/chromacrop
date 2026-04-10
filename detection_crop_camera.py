import asyncio
from typing import Any, ClassVar, Dict, Mapping, Optional, Tuple
from typing_extensions import Self

import cv2
import numpy as np
from PIL import Image as PILImage

from viam.components.camera import Camera
from viam.media.utils.pil import pil_to_viam_image
from viam.media.video import CameraMimeType, ViamImage
from viam.module.types import Reconfigurable
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName, ResponseMetadata
from viam.resource.base import ResourceBase
from viam.resource.types import Model, ModelFamily
from viam.utils import ValueTypes


class DetectionCropCamera(Camera, Reconfigurable):
    MODEL: ClassVar[Model] = Model(
        ModelFamily("10zing", "chromacrop"), "detection-crop"
    )

    source_cam: Camera
    source_name: str
    hsv_lower: np.ndarray
    hsv_upper: np.ndarray
    padding: int
    segment_size_px: int

    @classmethod
    def new(cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]) -> Self:
        cam = cls(config.name)
        cam.reconfigure(config, dependencies)
        return cam

    @classmethod
    def validate_config(cls, config: ComponentConfig) -> Tuple[list, list]:
        fields = config.attributes.fields
        if "source" not in fields:
            raise ValueError("'source' camera name is required")
        if "detect_color" not in fields:
            raise ValueError("'detect_color' hex color is required (e.g. '#dcfe79')")
        return [fields["source"].string_value], []

    def reconfigure(self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]):
        fields = config.attributes.fields

        # Pull the source camera from dependencies
        self.source_name = fields["source"].string_value
        source_resource_name = Camera.get_resource_name(self.source_name)
        self.source_cam = dependencies[source_resource_name]

        # Convert hex color to HSV and build detection range
        hex_color = fields["detect_color"].string_value
        tolerance = fields["hue_tolerance_pct"].number_value if "hue_tolerance_pct" in fields else 0.05
        self.hsv_lower, self.hsv_upper = self._hex_to_hsv_range(hex_color, tolerance)

        # Padding around detected region (pixels)
        self.padding = int(fields["padding"].number_value) if "padding" in fields else 5

        # Minimum contour area to count as the border (filters noise)
        self.segment_size_px = int(fields["segment_size_px"].number_value) if "segment_size_px" in fields else 100

    @staticmethod
    def _hex_to_hsv_range(hex_color, hue_tolerance_pct):
        # Parse hex string like "#dcfe79" to BGR, then to HSV
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

        # Single-pixel BGR image for OpenCV conversion
        pixel = np.uint8([[[b, g, r]]])
        hsv_pixel = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
        h, s, v = int(hsv_pixel[0]), int(hsv_pixel[1]), int(hsv_pixel[2])

        # Hue tolerance as percentage of full hue range (0-179 in OpenCV)
        h_delta = int(179 * hue_tolerance_pct)

        # Saturation and value get generous fixed margins
        lower = np.array([max(0, h - h_delta), max(0, s - 60), max(0, v - 60)])
        upper = np.array([min(179, h + h_delta), 255, 255])
        return lower, upper

    async def get_image(
        self,
        mime_type: str = "",
        *,
        extra: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> ViamImage:
        # Grab frame from source camera
        raw = await self.source_cam.get_image(mime_type=CameraMimeType.JPEG)

        # Decode JPEG bytes to numpy array
        np_arr = np.frombuffer(raw.data, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # Crop to the detected color border region
        cropped = self._crop_to_color(frame)

        # Convert back to a ViamImage for downstream consumers
        pil_img = PILImage.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        return pil_to_viam_image(pil_img, CameraMimeType.JPEG)

    def _crop_to_color(self, frame: np.ndarray) -> np.ndarray:
        # Convert to HSV and threshold for the target color
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)

        # Morphological cleanup — close gaps, remove noise
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter out small contours below segment_size_px area
        contours = [c for c in contours if cv2.contourArea(c) >= self.segment_size_px]

        if not contours:
            # No matching color detected — return the full frame as fallback
            return frame

        # Largest contour = the border around the target area
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        # Pad the crop and clamp to frame bounds
        fh, fw = frame.shape[:2]
        x1 = max(0, x - self.padding)
        y1 = max(0, y - self.padding)
        x2 = min(fw, x + w + self.padding)
        y2 = min(fh, y + h + self.padding)

        return frame[y1:y2, x1:x2]

    async def get_images(self, *, timeout=None, **kwargs):
        raise NotImplementedError

    async def get_point_cloud(self, *, extra=None, timeout=None, **kwargs):
        raise NotImplementedError

    async def get_properties(self, *, timeout=None, **kwargs):
        return Camera.Properties(supports_pcd=False)

    async def do_command(self, command: Mapping[str, ValueTypes], *, timeout=None, **kwargs):
        raise NotImplementedError
