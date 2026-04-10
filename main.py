#!/usr/bin/env python3
import asyncio
from viam.module.module import Module
from detection_crop_camera import DetectionCropCamera

async def main():
    # Register our custom camera model and start the module
    module = Module.from_args()
    module.add_model_from_registry(DetectionCropCamera.API, DetectionCropCamera.MODEL)
    await module.start()

asyncio.run(main())
