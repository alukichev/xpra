# This file is part of Xpra.
# Copyright (C) 2014-2022 Antoine Martin <antoine@xpra.org>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from queue import Queue, Empty

from xpra.util import typedict
from xpra.gst_common import import_gst
from xpra.gst_pipeline import Pipeline, GST_FLOW_OK
from xpra.log import Logger

Gst = import_gst()
log = Logger("encoder", "gstreamer")


def get_version():
    return (5, 0)

def get_type():
    return "gstreamer"

def get_info():
    return {"version"   : get_version()}

def init_module():
    log("gstreamer.init_module()")

def cleanup_module():
    log("gstreamer.cleanup_module()")


class VideoPipeline(Pipeline):
    __generic_signals__ = Pipeline.__generic_signals__.copy()
    """
    Dispatch video encoding or decoding to a gstreamer pipeline
    """
    def init_context(self, encoding, width, height, colorspace, options=None):
        options = typedict(options or {})
        self.encoding = encoding
        self.width = width
        self.height = height
        self.colorspace = colorspace
        self.frames = 0
        self.frame_queue = Queue()
        self.pipeline_str = ""
        self.create_pipeline(options)
        self.src    = self.pipeline.get_by_name("src")
        self.src.set_property("format", Gst.Format.TIME)
        #self.src.set_caps(Gst.Caps.from_string(CAPS))
        self.sink   = self.pipeline.get_by_name("sink")
        self.sink.connect("new-sample", self.on_new_sample)
        self.sink.connect("new-preroll", self.on_new_preroll)
        self.start()

    def create_pipeline(self, options):
        raise NotImplementedError()

    def on_message(self, bus, message):
        if message.type == Gst.MessageType.NEED_CONTEXT and self.pipeline_str.find("vaapi")>=0:
            log("vaapi is requesting a context")
            return GST_FLOW_OK
        return super().on_message(bus, message)

    def on_new_preroll(self, _appsink):
        log("new-preroll")
        return GST_FLOW_OK

    def process_buffer(self, buf):
        r = self.src.emit("push-buffer", buf)
        if r!=GST_FLOW_OK:
            log.error("Error: unable to push image buffer")
            return None
        try:
            return self.frame_queue.get(timeout=2 if self.frames==0 else 1)
        except Empty:
            log.error("Error: frame queue timeout")
            return None


    def get_info(self) -> dict:
        info = get_info()
        if self.colorspace is None:
            return info
        info.update({
            "frames"    : self.frames,
            "width"     : self.width,
            "height"    : self.height,
            "encoding"  : self.encoding,
            "colorspace": self.colorspace,
            "version"   : get_version(),
            })
        return info

    def __repr__(self):
        if self.colorspace is None:
            return "gstreamer(uninitialized)"
        return f"gstreamer({self.colorspace} - {self.width}x{self.height})"

    def is_ready(self):
        return self.colorspace is not None

    def is_closed(self):
        return self.colorspace is None


    def get_encoding(self):
        return self.encoding

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_type(self):
        return "gstreamer"

    def clean(self):
        super().cleanup()
        self.width = 0
        self.height = 0
        self.colorspace = None
        self.encoding = ""
        self.dst_formats = []
        self.frames = 0


    def do_emit_info(self):
        pass
