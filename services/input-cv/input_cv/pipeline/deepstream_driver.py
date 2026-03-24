"""
DeepStream local-device pipeline driver.

Requires: nvcr.io DeepStream container with pyds and GStreamer installed.
This module is only imported by main.py at runtime — never by any other
module, ensuring the test suite runs without DeepStream.

Pipeline topology (V4L2 / CSI local device):
  v4l2src device={device_path}
    -> capsfilter (pixel_format, width, height, fps)
    -> nvvideoconvert
    -> nvstreammux
    -> nvinfer (person detection, e.g. peoplenet)
    -> nvtracker
    -> appsink (metadata extraction callback)

Privacy guarantee:
  read_metadata() returns only aggregate counts and confidence values.
  No pixel buffer, frame URL, base64 data, face embedding, or bounding
  box coordinate is included in the returned dict.
  Bounding boxes are used only to compute person_count and are discarded
  before the dict is returned.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from .abstract import DeviceNotFoundError, PipelineDriver, PipelineReadError

logger = logging.getLogger(__name__)


class DeepStreamDriver(PipelineDriver):
    """
    Concrete DeepStream V4L2 pipeline driver.

    Args:
        device_path: local V4L2 device path, e.g. /dev/video0
        pixel_format: capture pixel format (NV12 recommended for Jetson)
        width: capture width in pixels
        height: capture height in pixels
        fps: capture frame rate
        startup_timeout_ms: max ms to wait for pipeline to start
        read_timeout_ms: max ms to wait for a metadata frame before declaring stall
    """

    def __init__(
        self,
        device_path: str,
        pixel_format: str,
        width: int,
        height: int,
        fps: int,
        startup_timeout_ms: int = 10000,
        read_timeout_ms: int = 3000,
    ) -> None:
        self._device_path = device_path
        self._pixel_format = pixel_format
        self._width = width
        self._height = height
        self._fps = fps
        self._startup_timeout_ms = startup_timeout_ms
        self._read_timeout_ms = read_timeout_ms
        self._pipeline: Any = None
        self._latest_metadata: list[dict] = []

    def open(self) -> None:
        if not os.path.exists(self._device_path):
            raise DeviceNotFoundError(
                f"Local camera device not found: {self._device_path}. "
                "Ensure the CSI camera is connected and the kernel module is loaded."
            )

        if not os.access(self._device_path, os.R_OK):
            raise DeviceNotFoundError(
                f"No read permission on {self._device_path}. "
                "Ensure the service user is in the 'video' group."
            )

        try:
            # Late import: pyds and gi are only available inside the DeepStream container.
            import gi  # noqa: PLC0415
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst  # noqa: PLC0415

            Gst.init(None)
            self._pipeline = self._build_pipeline(Gst)
            self._pipeline.set_state(Gst.State.PLAYING)
            logger.info(
                "input-cv: DeepStream pipeline started on %s (%dx%d @ %dfps %s)",
                self._device_path,
                self._width,
                self._height,
                self._fps,
                self._pixel_format,
            )
        except Exception as exc:
            raise RuntimeError(f"input-cv: pipeline initialization failed: {exc}") from exc

    def _build_pipeline(self, Gst: Any) -> Any:  # noqa: N803
        """
        Construct the GStreamer pipeline string and parse it.

        The appsink callback populates self._latest_metadata with
        aggregate detection results only — no pixel data.
        """
        pipeline_str = (
            f"v4l2src device={self._device_path} "
            f"! video/x-raw,format={self._pixel_format},"
            f"width={self._width},height={self._height},framerate={self._fps}/1 "
            "! nvvideoconvert "
            "! video/x-raw(memory:NVMM),format=NV12 "
            "! nvstreammux name=mux batch-size=1 "
            f"  width={self._width} height={self._height} batched-push-timeout=4000000 "
            "! nvinfer config-file-path=/app/models/peoplenet/config_infer.txt "
            "! nvtracker tracker-width=640 tracker-height=384 "
            "! nvmsgconv config=/app/models/msgconv_config.txt "
            "! appsink name=obs_sink emit-signals=True max-buffers=1 drop=True"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("obs_sink")
        appsink.connect("new-sample", self._on_new_sample)
        return pipeline

    def _on_new_sample(self, appsink: Any) -> Any:
        """
        GStreamer appsink callback.

        Extracts person count and mean confidence from the DeepStream
        metadata attached to the sample buffer. No pixel data is accessed.
        """
        try:
            import pyds  # noqa: PLC0415
            from gi.repository import Gst  # noqa: PLC0415

            sample = appsink.emit("pull-sample")
            buf = sample.get_buffer()

            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
            person_count = 0
            confidence_sum = 0.0
            obj_count = 0

            for frame_meta in pyds.NvDsFrameMetaList(batch_meta.frame_meta_list):
                frame = pyds.NvDsFrameMeta.cast(frame_meta.data)
                for obj_meta in pyds.NvDsObjectMetaList(frame.obj_meta_list):
                    obj = pyds.NvDsObjectMeta.cast(obj_meta.data)
                    # class_id 0 = person in PeopleNet
                    if obj.class_id == 0:
                        person_count += 1
                        confidence_sum += obj.confidence
                        obj_count += 1

            self._latest_metadata = [
                {
                    "frame_seq": getattr(batch_meta, "frame_number", 0),
                    "person_count": person_count,
                    "confidence_mean": (
                        confidence_sum / obj_count if obj_count > 0 else 0.0
                    ),
                    "pipeline_fps": self._fps,
                    "inference_ms": None,
                }
            ]
            return Gst.FlowReturn.OK
        except Exception as exc:
            logger.error("input-cv: metadata extraction error: %s", exc)
            return Gst.FlowReturn.ERROR

    def read_metadata(self) -> list[dict]:
        if self._pipeline is None:
            raise PipelineReadError("Pipeline is not open.")
        return list(self._latest_metadata)

    def close(self) -> None:
        if self._pipeline is not None:
            try:
                from gi.repository import Gst  # noqa: PLC0415
                self._pipeline.set_state(Gst.State.NULL)
            except Exception as exc:
                logger.warning("input-cv: error stopping pipeline: %s", exc)
            finally:
                self._pipeline = None
        logger.info("input-cv: DeepStream pipeline closed.")
