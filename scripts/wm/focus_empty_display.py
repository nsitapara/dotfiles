"""Activate an empty desktop with one click using public CoreGraphics APIs."""
import ctypes
import plistlib


class Point(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double)]


def click_empty_desktop(frame):
    cg = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
    cf.CFPropertyListCreateData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_ulong, ctypes.c_void_p]
    cf.CFPropertyListCreateData.restype = ctypes.c_void_p
    cf.CFDataGetLength.argtypes = [ctypes.c_void_p]
    cf.CFDataGetLength.restype = ctypes.c_long
    cf.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
    cf.CFDataGetBytePtr.restype = ctypes.c_void_p
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    info = cg.CGWindowListCopyWindowInfo(1 | 16, 0)  # On-screen, excluding desktop elements.
    if not info:
        raise RuntimeError('Could not inspect windows on the empty display')
    try:
        data = cf.CFPropertyListCreateData(None, info, 100, 0, None)
        if not data:
            raise RuntimeError('Could not read desktop window bounds')
        try:
            windows = plistlib.loads(ctypes.string_at(cf.CFDataGetBytePtr(data), cf.CFDataGetLength(data)))
        finally:
            cf.CFRelease(data)
    finally:
        cf.CFRelease(info)
    bounds = [w['kCGWindowBounds'] for w in windows if w.get('kCGWindowAlpha', 1) > 0]
    point = None
    for fx, fy in ((.5,.5),(.25,.5),(.75,.5),(.5,.75),(.5,.25)):
        candidate = Point(frame['x'] + frame['w']*fx, frame['y'] + frame['h']*fy)
        if not any(b['X'] <= candidate.x <= b['X']+b['Width'] and b['Y'] <= candidate.y <= b['Y']+b['Height'] for b in bounds):
            point = candidate
            break
    if point is None:
        raise RuntimeError('No uncovered desktop point on the target display; refusing to click an application')
    cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, Point, ctypes.c_uint32]
    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    for event_type in (5, 1, 2):  # Mouse moved, left down, left up. Never double-click.
        event = cg.CGEventCreateMouseEvent(None, event_type, point, 0)
        if not event:
            raise RuntimeError('Could not create desktop focus event')
        try:
            cg.CGEventPost(0, event)
        finally:
            cf.CFRelease(event)
